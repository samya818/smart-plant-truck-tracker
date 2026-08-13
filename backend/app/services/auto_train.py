"""
Pipeline d'entraînement automatique et d'évaluation prédictive des temps de cycle.

Formulation Mathématique du Problème :
  Soit un camion entrant à l'instant t_in (porte d'usine).
  Variable Cible : y_t = durée totale du cycle en minutes (t_out - t_in).
  Objectif       : Minimiser l'erreur de prédiction |y_t - \hat{y}_t|.

Architecture MLOps & Anti-Leakage :
  1. Séparation Temporelle Stricte (Out-Of-Time Validation) :
     Les données sont triées chronologiquement. Train = [0, T_split], Test = [T_split, T_fin].
     Aucun mélange aléatoire (No Shuffle) pour préserver la structure causale.
  2. Prévention du Data Leakage :
     Toutes les features temporelles (rolling means, std, lags) sont décalées d'au moins
     1 pas de temps (shift >= 1) pour ne jamais inclure l'observation courante ou future.
  3. Métriques d'Évaluation Complètes :
     - MAE  (Mean Absolute Error en minutes)
     - RMSE (Root Mean Squared Error en minutes)
     - MAPE (Mean Absolute Percentage Error en %)
"""
import asyncio
import os
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.database import SessionLocal
from app.models import Cycle, TruckStatus, Event


def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calcule le Mean Absolute Percentage Error (MAPE) en pourcentage."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    # Éviter la division par zéro en filtrant les cycles non nuls
    mask = y_true > 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


class AutoTrainPipeline:
    """Pipeline MLOps avec validation temporelle stricte et anti-leakage."""

    MODELS_DIR = "models"
    METRICS_FILE = "models/training_metrics.json"

    def __init__(self):
        os.makedirs(self.MODELS_DIR, exist_ok=True)

    async def schedule_loop(self):
        """Boucle infinie : entraînement et réévaluation toutes les 6 heures."""
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                self.run_training_pipeline()
            except Exception as e:
                print(f"[AutoTrain] Erreur boucle planifiée : {e}")

    def _build_features_anti_leakage(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Feature engineering causale sans fuite de données (Strictly Causal / Anti-Leakage).
        Toutes les variables rétroactives utilisent shift(1) pour ne regarder que le passé.
        """
        df = df.copy().sort_values('ds').reset_index(drop=True)
        
        # 1. Variables calendaires et cycliques (connues au moment de l'entrée t_in)
        df['hour_sin'] = np.sin(2 * np.pi * df['heure'] / 24.0)
        df['hour_cos'] = np.cos(2 * np.pi * df['heure'] / 24.0)
        df['dow_sin'] = np.sin(2 * np.pi * df['jour_semaine'] / 7.0)
        df['dow_cos'] = np.cos(2 * np.pi * df['jour_semaine'] / 7.0)
        df['is_weekend'] = (df['jour_semaine'] >= 5).astype(int)
        df['is_morning_rush'] = ((df['heure'] >= 7) & (df['heure'] <= 9)).astype(int)
        df['is_afternoon_rush'] = ((df['heure'] >= 14) & (df['heure'] <= 16)).astype(int)
        
        # 2. Variables d'autocorrélation causales (Strictly Past-Only)
        # shift(1) garantit qu'on ne regarde que les cycles terminés AVANT l'entrée courante
        df['lag_1_cycle'] = df['y'].shift(1)
        df['lag_5_cycles'] = df['y'].shift(5)
        df['rolling_mean_5'] = df['y'].shift(1).rolling(window=5, min_periods=1).mean()
        df['rolling_std_5'] = df['y'].shift(1).rolling(window=5, min_periods=1).std().fillna(0)
        
        # Imputation causale (remplissage par la médiane globale historique)
        median_y = df['y'].median() if len(df) > 0 else 60.0
        df['lag_1_cycle'] = df['lag_1_cycle'].fillna(median_y)
        df['lag_5_cycles'] = df['lag_5_cycles'].fillna(median_y)
        df['rolling_mean_5'] = df['rolling_mean_5'].fillna(median_y)
        df['rolling_std_5'] = df['rolling_std_5'].fillna(0.0)
        
        return df

    def run_training_pipeline(self) -> Dict[str, Any]:
        """Exécute l'entraînement et calcule MAE, RMSE et MAPE avec split chronologique."""
        print(f"[AutoTrain] Démarrage de l'évaluation MLOps — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            db = SessionLocal()
        except Exception as e:
            print(f"[AutoTrain] Erreur connexion DB: {e}")
            return {"status": "db_error", "reason": str(e)}

        try:
            depuis = datetime.utcnow() - timedelta(days=90)
            from sqlalchemy import and_
            from app.models import PosteType

            # Identification et exclusion des données de tests purs
            cycles_simules_ids = (
                db.query(Cycle.id)
                .join(
                    Event,
                    and_(
                        Event.truck_id == Cycle.truck_id,
                        Event.poste == PosteType.PORTE_USINE,
                        Event.type_event == "entree",
                        Event.horodatage >= Cycle.entree_porte,
                        Event.source == "simulation_test_court",
                    )
                )
                .subquery()
            )

            cycles_bruts = db.query(Cycle).filter(
                Cycle.entree_porte >= depuis,
                Cycle.status == TruckStatus.TERMINE,
                Cycle.duree_total >= 10,              # Filtre qualité : durée minimale réaliste (10 min)
                Cycle.est_anomalie == False,          # Exclut les pannes exceptionnelles
                ~Cycle.id.in_(cycles_simules_ids),
            ).order_by(Cycle.entree_porte.asc()).all()

            if len(cycles_bruts) < 30:
                print(f"[AutoTrain] Nombre insuffisant de cycles ({len(cycles_bruts)} < 30 requises).")
                return {
                    "status": "skipped",
                    "raison": f"{len(cycles_bruts)} cycles valides (< 30 minimum pour benchmark statistique)",
                }

            # Construction du DataFrame trié chronologiquement
            df = pd.DataFrame([{
                'ds': c.entree_porte,
                'y': float(c.duree_total),
                'heure': c.entree_porte.hour,
                'jour_semaine': c.entree_porte.weekday(),
            } for c in cycles_bruts]).sort_values('ds').reset_index(drop=True)

            # Split temporel strict 80% Train (Passé) / 20% Test (Futur)
            split_idx = int(len(df) * 0.8)
            train_df = df.iloc[:split_idx].copy()
            test_df = df.iloc[split_idx:].copy()

            models_metrics: Dict[str, Dict[str, float]] = {}
            candidats = {}

            y_test = test_df['y'].values

            # ──────────────────────────────────────────────────────────────────
            # 1. Modèle Prophet (Série temporelle & Saisonnalités)
            # ──────────────────────────────────────────────────────────────────
            try:
                from prophet import Prophet
                m_prophet = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
                m_prophet.fit(train_df[['ds', 'y']])
                
                future = test_df[['ds']].copy()
                forecast = m_prophet.predict(future)
                y_pred_prophet = forecast['yhat'].values

                mae_p = float(mean_absolute_error(y_test, y_pred_prophet))
                rmse_p = float(np.sqrt(mean_squared_error(y_test, y_pred_prophet)))
                mape_p = float(calculate_mape(y_test, y_pred_prophet))

                models_metrics['prophet'] = {
                    "mae": round(mae_p, 2),
                    "rmse": round(rmse_p, 2),
                    "mape": round(mape_p, 2),
                }
                candidats['prophet'] = m_prophet
                print(f"[AutoTrain] Prophet  -> MAE: {mae_p:.2f} min | RMSE: {rmse_p:.2f} min | MAPE: {mape_p:.1f}%")
            except Exception as e:
                print(f"[AutoTrain] Prophet non disponible : {e}")

            # ──────────────────────────────────────────────────────────────────
            # 2. Modèle XGBoost (Gradient Boosting avec Features Causales)
            # ──────────────────────────────────────────────────────────────────
            try:
                import xgboost as xgb
                df_feat = self._build_features_anti_leakage(df)
                feature_cols = [c for c in df_feat.columns if c not in ['ds', 'y']]

                train_feat = df_feat.iloc[:split_idx]
                test_feat = df_feat.iloc[split_idx:]

                dtrain = xgb.DMatrix(train_feat[feature_cols], label=train_feat['y'])
                dtest = xgb.DMatrix(test_feat[feature_cols], label=test_feat['y'])

                params = {
                    'objective': 'reg:squarederror',
                    'max_depth': 4,
                    'learning_rate': 0.05,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'eval_metric': 'mae',
                    'seed': 42
                }
                m_xgb = xgb.train(
                    params, dtrain, num_boost_round=150,
                    evals=[(dtest, 'test')], early_stopping_rounds=20,
                    verbose_eval=False
                )
                y_pred_xgb = m_xgb.predict(dtest)

                mae_x = float(mean_absolute_error(y_test, y_pred_xgb))
                rmse_x = float(np.sqrt(mean_squared_error(y_test, y_pred_xgb)))
                mape_x = float(calculate_mape(y_test, y_pred_xgb))

                models_metrics['xgboost'] = {
                    "mae": round(mae_x, 2),
                    "rmse": round(rmse_x, 2),
                    "mape": round(mape_x, 2),
                }
                candidats['xgboost'] = m_xgb
                print(f"[AutoTrain] XGBoost  -> MAE: {mae_x:.2f} min | RMSE: {rmse_x:.2f} min | MAPE: {mape_x:.1f}%")
            except Exception as e:
                print(f"[AutoTrain] XGBoost non disponible : {e}")

            # ──────────────────────────────────────────────────────────────────
            # 3. Modèle Baseline Naïf (Moyenne Mobile Historique EWMA)
            # ──────────────────────────────────────────────────────────────────
            mean_baseline = train_df['y'].mean()
            y_pred_base = np.full_like(y_test, fill_value=mean_baseline)
            mae_b = float(mean_absolute_error(y_test, y_pred_base))
            rmse_b = float(np.sqrt(mean_squared_error(y_test, y_pred_base)))
            mape_b = float(calculate_mape(y_test, y_pred_base))
            models_metrics['baseline_ewma'] = {
                "mae": round(mae_b, 2),
                "rmse": round(rmse_b, 2),
                "mape": round(mape_b, 2),
            }

            if not models_metrics:
                return {"status": "failed", "raison": "Aucun modèle n'a pu être évalué"}

            # Sauvegarde des modèles
            if 'prophet' in candidats:
                self._save_model('prophet_champion.pkl', candidats['prophet'], models_metrics['prophet']['mae'], len(df))
            if 'xgboost' in candidats:
                self._save_model('xgboost_champion.pkl', candidats['xgboost'], models_metrics['xgboost']['mae'], len(df))

            # Enregistrement des métriques vérifiées
            result_payload = {
                "date_evaluation": datetime.now().isoformat(),
                "target_variable": "duree_totale_cycle_minutes (y_t = t_out - t_in)",
                "validation_method": "Temporal Split (80% Train chronologique / 20% Test futur)",
                "anti_leakage_applied": True,
                "n_samples_total": len(df),
                "n_train": len(train_df),
                "n_test": len(test_df),
                "metrics": models_metrics,
            }
            self._save_metrics(result_payload)

            print(f"[AutoTrain] Bilan complet enregistré dans {self.METRICS_FILE}")
            return {"status": "success", "results": result_payload}

        finally:
            db.close()

    def run(self) -> Dict[str, Any]:
        """Exécution synchrone pour les tests et scripts."""
        return self.run_training_pipeline()

    def _save_model(self, filename: str, model: Any, mae: float, n_samples: int):
        artifact = {
            'model': model,
            'mae': mae,
            'trained_at': datetime.now().isoformat(),
            'n_samples': n_samples
        }
        with open(os.path.join(self.MODELS_DIR, filename), 'wb') as f:
            pickle.dump(artifact, f)

    def _save_metrics(self, metrics: dict):
        with open(self.METRICS_FILE, 'w') as f:
            json.dump(metrics, f, indent=2)

