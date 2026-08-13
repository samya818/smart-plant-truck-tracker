"""
Pipeline de Machine Learning Automatique & MLOps Industriel.

Règles de validation & Rigueur scientifique :
1. Variable Cible Formelle : y_t = duree_totale_cycle_minutes (t_out - t_in).
2. Anti-Leakage Strict : Aucune feature ne regarde dans le futur (shift(1)).
3. Médiane d'imputation calculée EXCLUSIVEMENT sur le train set.
4. 3-Way Temporal Split : 70% Train (Passé) / 15% Validation (Early Stopping) / 15% Test (Futur Indépendant).
5. Champion vs Challenger : Remplacement en production uniquement si MAE_test s'améliore (Zéro Régression).
6. Multi-Métriques : MAE, RMSE, MAPE comparées à la baseline naïve (Moyenne Train).
"""
import os
import pickle
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.database import SessionLocal
from app.models import Cycle, TruckStatus
from app.services.feature_engineering import (
    build_features_matrix_train, FEATURE_COLUMNS,
    get_valid_ml_cycles, ML_TRAINING_THRESHOLD, ML_PRODUCTION_THRESHOLD
)

def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error avec protection division par zéro."""
    mask = y_true > 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)

class AutoTrainPipeline:
    """Gestionnaire MLOps de réentraînement automatique."""

    def __init__(self):
        self.MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
        os.makedirs(self.MODEL_DIR, exist_ok=True)
        self.METRICS_FILE = os.path.join(self.MODEL_DIR, "training_metrics.json")

    def run_training_pipeline(self) -> Dict[str, Any]:
        """Exécute le pipeline complet avec 3-way temporal split et anti-leakage."""
        db = SessionLocal()
        try:
            print("[AutoTrain] Démarrage du pipeline d'entraînement temporel...")

            # Extraction des cycles réels via la politique centralisée (MÊME critères que PredictionService)
            cycles_bruts = get_valid_ml_cycles(db, Cycle, TruckStatus)

            if len(cycles_bruts) < ML_TRAINING_THRESHOLD:
                print(f"[AutoTrain] Nombre insuffisant de cycles ({len(cycles_bruts)} < {ML_TRAINING_THRESHOLD} requises).")
                return {
                    "status": "skipped",
                    "raison": f"{len(cycles_bruts)} cycles valides (< {ML_TRAINING_THRESHOLD} minimum pour benchmark statistique)",
                }

            # Construction du DataFrame trié chronologiquement
            df = pd.DataFrame([{
                'entree_porte': c.entree_porte,
                'ds': c.entree_porte,
                'y': float(c.duree_total),
            } for c in cycles_bruts]).sort_values('ds').reset_index(drop=True)

            # ── 3-WAY TEMPORAL SPLIT (70% Train / 15% Val / 15% Test) ────────
            n_total = len(df)
            idx_train = int(n_total * 0.70)
            idx_val = int(n_total * 0.85)

            train_df = df.iloc[:idx_train].copy()
            val_df = df.iloc[idx_train:idx_val].copy()
            test_df = df.iloc[idx_val:].copy()

            # Anti-Leakage Absolu : Calcul de la médiane UNIQUEMENT sur le set Train
            train_median_y = float(train_df['y'].median()) if not train_df.empty else 90.0

            # Construction des matrices de features via le module centralisé
            df_feat, _ = build_features_matrix_train(df, train_median_y=train_median_y)

            train_feat = df_feat.iloc[:idx_train]
            val_feat = df_feat.iloc[idx_train:idx_val]
            test_feat = df_feat.iloc[idx_val:]

            models_metrics: Dict[str, Dict[str, float]] = {}
            candidats = {}

            y_test = test_df['y'].values

            # ──────────────────────────────────────────────────────────────────
            # 1. Modèle Prophet (Série temporelle & Saisonnalités)
            # ──────────────────────────────────────────────────────────────────
            try:
                from prophet import Prophet
                m_prophet = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
                # Entraînement sur train + validation pour maximiser l'historique
                train_val_df = pd.concat([train_df, val_df])
                m_prophet.fit(train_val_df[['ds', 'y']])
                
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
            # 2. Modèle XGBoost (Gradient Boosting avec Early Stopping sur Val)
            # ──────────────────────────────────────────────────────────────────
            try:
                import xgboost as xgb
                dtrain = xgb.DMatrix(train_feat[FEATURE_COLUMNS], label=train_feat['y'])
                dval = xgb.DMatrix(val_feat[FEATURE_COLUMNS], label=val_feat['y'])
                dtest = xgb.DMatrix(test_feat[FEATURE_COLUMNS], label=test_feat['y'])

                params = {
                    'objective': 'reg:squarederror',
                    'max_depth': 4,
                    'learning_rate': 0.05,
                    'subsample': 0.8,
                    'colsample_bytree': 0.8,
                    'eval_metric': 'mae',
                    'seed': 42
                }
                # Early stopping sur le set de VALIDATION (le TEST set reste 100% aveugle)
                m_xgb = xgb.train(
                    params, dtrain, num_boost_round=200,
                    evals=[(dval, 'val')], early_stopping_rounds=15,
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
            # 3. Modèle Baseline Naïf (Moyenne Historique du Train Set)
            # ──────────────────────────────────────────────────────────────────
            mean_baseline = float(train_df['y'].mean())
            y_pred_base = np.full_like(y_test, fill_value=mean_baseline)
            mae_b = float(mean_absolute_error(y_test, y_pred_base))
            rmse_b = float(np.sqrt(mean_squared_error(y_test, y_pred_base)))
            mape_b = float(calculate_mape(y_test, y_pred_base))
            models_metrics['baseline_mean'] = {
                "mae": round(mae_b, 2),
                "rmse": round(rmse_b, 2),
                "mape": round(mape_b, 2),
            }

            if not models_metrics:
                return {"status": "failed", "raison": "Aucun modèle n'a pu être évalué"}

            # Sauvegarde conditionnelle des modèles (Champion vs Challenger)
            # On passe aussi la MAE de la baseline pour normaliser la comparaison cross-dataset
            baseline_mae = models_metrics['baseline_mean']['mae']
            if 'prophet' in candidats:
                self._save_model('prophet_champion.pkl', candidats['prophet'], models_metrics['prophet'], len(df), train_median_y, baseline_mae)
            if 'xgboost' in candidats:
                self._save_model('xgboost_champion.pkl', candidats['xgboost'], models_metrics['xgboost'], len(df), train_median_y, baseline_mae)

            # Enregistrement des métriques vérifiées
            result_payload = {
                "date_evaluation": datetime.now().isoformat(),
                "target_variable": "duree_totale_cycle_minutes (y_t = t_out - t_in)",
                "validation_method": "3-Way Temporal Split (70% Train / 15% Val Early Stopping / 15% Test Indépendant)",
                "anti_leakage_applied": True,
                "feature_schema_version": "2.0.0",
                "train_median_imputed": round(train_median_y, 2),
                "n_samples_total": len(df),
                "n_train": len(train_df),
                "n_val": len(val_df),
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

    def _save_model(
        self, filename: str, model: Any, metrics: dict,
        n_samples: int, train_median: float, baseline_mae: float = 1.0
    ):
        """
        Sauvegarde conditionnelle (Champion vs Challenger) avec versionnement d'artefact.

        Problème de comparaison cross-dataset :
        Comme le dataset grandit entre deux réentraînements (le test_1 ≠ test_2),
        comparer MAE absolues est statistiquement biaisé. On utilise à la place
        le ratio MAE_relative = MAE_candidat / MAE_baseline qui est normalisé
        par rapport au niveau de difficulté du dataset courant.

        Exemple :
            Réentraînement J1 : MAE_candidat=12min, MAE_baseline=20min → relative=0.60
            Réentraînement J2 : MAE_candidat=13min, MAE_baseline=22min → relative=0.59
            Malgré une MAE absolue plus élevée, le candidat J2 est promu car
            il performe mieux relativement à son propre dataset.
        """
        path = os.path.join(self.MODEL_DIR, filename)
        new_mae = metrics.get('mae', float('inf'))
        # MAE relative = MAE / baseline_mae (normalisée par la difficulté du dataset)
        new_relative_mae = new_mae / max(baseline_mae, 0.1)

        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    old_artifact = pickle.load(f)
                old_relative_mae = old_artifact.get('relative_mae', float('inf'))
                if new_relative_mae >= old_relative_mae:
                    print(
                        f"[AutoTrain] 🛑 Candidat REJETÉ pour {filename} : "
                        f"MAE_rel={new_relative_mae:.3f} >= Champion MAE_rel={old_relative_mae:.3f} "
                        f"(MAE abs: {new_mae:.2f}m vs baseline {baseline_mae:.2f}m)"
                    )
                    return
                else:
                    print(
                        f"[AutoTrain] 🏆 Nouveau Champion pour {filename} : "
                        f"MAE_rel={new_relative_mae:.3f} < Ancien={old_relative_mae:.3f} "
                        f"(MAE abs: {new_mae:.2f}m, gain relatif: {(old_relative_mae-new_relative_mae)*100:.1f}pp)"
                    )
            except Exception as e:
                print(f"[AutoTrain] Impossible de lire l'ancien champion ({e}), sauvegarde forcée.")

        artifact = {
            'model': model,
            'mae': new_mae,
            'relative_mae': new_relative_mae,   # Pour comparaison cross-dataset
            'baseline_mae': baseline_mae,
            'metrics': metrics,
            'feature_schema_version': "2.0.0",
            'feature_names': FEATURE_COLUMNS,
            'train_median_imputed': train_median,
            'trained_at': datetime.now().isoformat(),
            'n_samples': n_samples,
        }
        with open(path, 'wb') as f:
            pickle.dump(artifact, f)
        print(f"[AutoTrain] Modèle {filename} (v2.0.0) enregistré avec succès ✓")

    def _save_metrics(self, metrics: dict):
        with open(self.METRICS_FILE, 'w') as f:
            json.dump(metrics, f, indent=2)
