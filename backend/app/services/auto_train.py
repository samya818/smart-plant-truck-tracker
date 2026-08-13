"""
Pipeline d'entraînement automatique — Prophet prioritaire + XGBoost expérimental.
Champion = Prophet (production). Challenger XGBoost = toggle manuel uniquement.

Règle de qualité des données :
  - Cycles simulés (source = "simulation" sur l'Event d'entrée) → EXCLUS
  - Cycles marqués est_anomalie=True → EXCLUS
  Seuls des cycles réels, complets, non-anomaliques alimentent le modèle.
"""
import asyncio
import os
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, Any
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.database import SessionLocal
from app.models import Cycle, TruckStatus, Event


class AutoTrainPipeline:
    """MLOps simplifié : Prophet en production, XGBoost en mode recherche."""

    MODELS_DIR = "models"
    METRICS_FILE = "models/training_metrics.json"

    def __init__(self):
        os.makedirs(self.MODELS_DIR, exist_ok=True)

    async def schedule_loop(self):
        """Boucle infinie : entraînement toutes les 6 heures."""
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                self.run_training_pipeline()
            except Exception as e:
                print(f"[AutoTrain] Erreur : {e}")

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Feature engineering pour XGBoost (mode expérimental)."""
        df = df.copy()
        df['hour_sin'] = np.sin(2 * np.pi * df['heure'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['heure'] / 24)
        df['dow_sin'] = np.sin(2 * np.pi * df['jour_semaine'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['jour_semaine'] / 7)
        df['is_weekend'] = (df['jour_semaine'] >= 5).astype(int)
        df['is_morning_rush'] = ((df['heure'] >= 7) & (df['heure'] <= 9)).astype(int)
        df['is_afternoon_rush'] = ((df['heure'] >= 14) & (df['heure'] <= 16)).astype(int)
        df['lag_1d'] = df['y'].shift(24)
        df['lag_7d'] = df['y'].shift(24 * 7)
        df['rolling_mean_24h'] = df['y'].shift(1).rolling(window=24, min_periods=1).mean()
        df['rolling_std_24h'] = df['y'].shift(1).rolling(window=24, min_periods=1).std().fillna(0)
        df = df.fillna(df.median(numeric_only=True)).fillna(0)
        return df

    def run_training_pipeline(self) -> Dict[str, Any]:
        print(f"[AutoTrain] Démarrage — {datetime.now()}")

        try:
            db = SessionLocal()
        except Exception as e:
            print(f"[AutoTrain] DB connection failed: {e}")
            return {"status": "db_error", "reason": str(e)}

        try:
            # 1. CHARGEMENT — données réelles uniquement
            # Règle d'exclusion :
            #   a) est_anomalie=True  → durée corrompue ou cycle non représentatif
            #   b) source=simulation  → 6 plaques en boucle, pas de vraie diversité
            #      (on détecte la source via l'event d'entrée PORTE_USINE du cycle)
            depuis = datetime.utcnow() - timedelta(days=90)

            # Sous-requête : IDs des cycles dont l'event d'entrée est de source simulation
            from sqlalchemy import exists, and_
            from app.models import PosteType

            cycles_simules_ids = (
                db.query(Cycle.id)
                .join(
                    Event,
                    and_(
                        Event.truck_id == Cycle.truck_id,
                        Event.poste == PosteType.PORTE_USINE,
                        Event.type_event == "entree",
                        Event.horodatage >= Cycle.entree_porte,
                        Event.source == "simulation",
                    )
                )
                .subquery()
            )

            cycles_bruts = db.query(Cycle).filter(
                Cycle.entree_porte >= depuis,
                Cycle.status == TruckStatus.TERMINE,
                Cycle.duree_total > 0,
                Cycle.est_anomalie == False,          # exclut cycles corrompus
                ~Cycle.id.in_(cycles_simules_ids),    # exclut cycles simulés
            ).all()

            n_total_termine = db.query(Cycle).filter(
                Cycle.entree_porte >= depuis,
                Cycle.status == TruckStatus.TERMINE,
                Cycle.duree_total > 0,
            ).count()
            n_exclus = n_total_termine - len(cycles_bruts)

            print(
                f"[AutoTrain] {len(cycles_bruts)} cycles réels retenus "
                f"({n_exclus} exclus : simulation ou anomalie)"
            )

            cycles = cycles_bruts

            if len(cycles) < 100:
                return {
                    "status": "skipped",
                    "raison": (
                        f"{len(cycles)} cycles réels < 100 minimum. "
                        f"({n_exclus} cycles exclus car simulés/anomalies)"
                    ),
                }

            # 2. PRÉPARATION
            df = pd.DataFrame([{
                'ds': c.entree_porte,
                'y': c.duree_total,
                'heure': c.entree_porte.hour,
                'jour_semaine': c.entree_porte.weekday(),
                'parking': c.duree_parking,
                'ensachage': c.duree_ensachage,
                'bascule': c.duree_bascule_tare + c.duree_bascule_brut,
            } for c in cycles])

            # Split chronologique
            split_idx = int(len(df) * 0.8)
            train_df = df.iloc[:split_idx].copy()
            test_df = df.iloc[split_idx:].copy()

            scores = {}
            candidats = {}

            # --- Champion : Prophet (production) ---
            try:
                from prophet import Prophet
                m = Prophet(daily_seasonality=True, yearly_seasonality=False)
                m.fit(train_df[['ds', 'y']].rename(columns={'ds': 'ds', 'y': 'y'}))
                future = test_df[['ds']].rename(columns={'ds': 'ds'})
                forecast = m.predict(future)
                pred_prophet = forecast['yhat'].values

                mae_prophet = mean_absolute_error(test_df['y'].values, pred_prophet)
                scores['prophet'] = round(mae_prophet, 2)
                candidats['prophet'] = m
                print(f"[AutoTrain] Prophet — MAE: {mae_prophet:.2f}")
            except Exception as e:
                print(f"[AutoTrain] Prophet failed: {e}")

            # --- Challenger : XGBoost (expérimental) ---
            try:
                import xgboost as xgb
                df_feat = self._build_features(df)
                train_feat = df_feat.iloc[:split_idx]
                test_feat = df_feat.iloc[split_idx:]
                feature_cols = [c for c in df_feat.columns if c not in ['ds', 'y']]

                dtrain = xgb.DMatrix(train_feat[feature_cols], label=train_feat['y'])
                dtest = xgb.DMatrix(test_feat[feature_cols], label=test_feat['y'])

                params = {
                    'objective': 'reg:squarederror',
                    'max_depth': 6, 'learning_rate': 0.05,
                    'subsample': 0.8, 'colsample_bytree': 0.8,
                    'eval_metric': 'mae', 'seed': 42
                }
                model_xgb = xgb.train(params, dtrain, num_boost_round=200,
                                      evals=[(dtest, 'test')],
                                      early_stopping_rounds=20, verbose_eval=False)
                pred_xgb = model_xgb.predict(dtest)
                mae_xgb = mean_absolute_error(test_feat['y'].values, pred_xgb)
                scores['xgboost'] = round(mae_xgb, 2)
                candidats['xgboost'] = model_xgb
                print(f"[AutoTrain] XGBoost — MAE: {mae_xgb:.2f}")
            except Exception as e:
                print(f"[AutoTrain] XGBoost failed: {e}")

            if not scores:
                return {"status": "failed", "raison": "Aucun modèle entraînable"}

            # 3. DÉPLOIEMENT — Prophet est TOUJOURS le champion production
            champion_mae = self._get_champion_mae()
            meilleur = min(scores, key=scores.get)

            # Sauvegarde Prophet (production)
            if 'prophet' in candidats:
                self._save_model('prophet_champion.pkl', candidats['prophet'], scores['prophet'], len(df))

            # Sauvegarde XGBoost (expérimental) si meilleur que Prophet
            if 'xgboost' in candidats and scores.get('xgboost', 999) < scores.get('prophet', 999) * 0.95:
                self._save_model('xgboost_champion.pkl', candidats['xgboost'], scores['xgboost'], len(df))
                print(f"[AutoTrain] XGBoost meilleur mais reste expérimental")

            self._save_metrics({
                "date": datetime.now().isoformat(),
                "champion": "prophet",
                "mae": scores.get('prophet'),
                "n_cycles": len(cycles),
                "n_exclus_simulation_anomalie": n_exclus,
                "all_scores": scores,
            })

            print(f"[AutoTrain] Terminé — Scores: {scores}")
            return {"status": "success", "scores": scores}

        finally:
            db.close()

    def run(self) -> Dict[str, Any]:
        """Alias for manual / CLI invocation."""
        return self.run_training_pipeline()

    def _save_model(self, filename, model, mae, n_samples):
        artifact = {
            'model': model,
            'mae': mae,
            'trained_at': datetime.now().isoformat(),
            'n_samples': n_samples
        }
        with open(f"models/{filename}", 'wb') as f:
            pickle.dump(artifact, f)

    def _get_champion_mae(self) -> float:
        if os.path.exists(self.METRICS_FILE):
            with open(self.METRICS_FILE) as f:
                data = json.load(f)
                return data.get("mae", 9999.0)
        return 9999.0

    def _save_metrics(self, metrics: dict):
        with open(self.METRICS_FILE, 'w') as f:
            json.dump(metrics, f, indent=2)
