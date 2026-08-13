"""
Service de Prédiction — Estimation du Temps Restant (Remaining-Time ETA) pour Camions Actifs.

Modélisation Mathématique Formelle :
1. Le modèle ML (Prophet / XGBoost) estime la durée totale du cycle : y_pred = E[T_total | t_in, contexte]
2. Le temps restant pour un camion actif est calculé selon son historique de présence :
   T_elapsed = (now - entree_porte) en minutes
   ETA_remaining = max(5.0, y_pred - T_elapsed)
3. Zero Feature Mismatch : Inférence XGBoost alimentée par feature_engineering.py.
"""
import os
import pickle
from datetime import datetime, timedelta
from typing import Optional, List
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models import Event, Cycle, PosteType, TruckStatus, EtapeConfig
from app.config import get_settings
from app.services.feature_engineering import (
    build_single_inference_vector,
    count_valid_ml_cycles,
    ML_TRAINING_THRESHOLD,
    ML_PRODUCTION_THRESHOLD,
)

settings = get_settings()

class PredictionService:
    """Service unifié de prédiction de l'ETA restant."""

    def __init__(self, db: Session):
        self.db = db
        self.MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
        self.niveau = self._detecter_niveau()

    def _detecter_niveau(self) -> int:
        """
        Détermine le palier d'apprentissage ML selon le nombre de cycles réels valides.

        Politique explicite (Option B) :
          Niveau 0 (< 30 cycles)  : Règles métier expertes (EtapeConfig)
          Niveau 1 (30-99 cycles) : EWMA sur les 7 derniers jours (ML expérimental)
          Niveau 2 (≥ 100 cycles) : Modèle ML champion (Prophet / XGBoost) en production

        IMPORTANT : on utilise count_valid_ml_cycles() qui applique EXACTEMENT
        les mêmes critères d'exclusion que get_valid_ml_cycles() dans AutoTrain :
        - Exclut les camions simulés (truck_ids 1-6)
        - Exclut les cycles anomalie (est_anomalie=True)
        - Exclut les cycles < 10 min
        Cela garantit que le niveau ML affiché correspond au volume qui a réellement
        servi à entraîner le modèle.
        """
        count = count_valid_ml_cycles(self.db, Cycle, TruckStatus)
        if count >= ML_PRODUCTION_THRESHOLD and os.path.exists(
            os.path.join(self.MODEL_DIR, "prophet_champion.pkl")
        ):
            return 2
        elif count >= ML_TRAINING_THRESHOLD:
            return 1
        return 0

    def predict_remaining_eta(
        self,
        poste_actuel: PosteType,
        entree_porte: Optional[datetime] = None,
        modele_prefere: str = "prophet"
    ) -> dict:
        """
        Prédit l'ETA restant (en minutes) pour un camion donné.
        Prend en compte le temps déjà écoulé depuis son entrée pour ajuster le temps résiduel.
        """
        now = datetime.utcnow()
        t_in = entree_porte or now
        if t_in.tzinfo is not None:
            t_in = t_in.replace(tzinfo=None)

        temps_deja_passe = max(0.0, (now - t_in).total_seconds() / 60.0)

        # 1. Estimation de la durée totale de cycle attendue
        if self.niveau >= 2:
            pred_total = self._predict_total_cycle_ml(t_in, modele_prefere)
        elif self.niveau >= 1:
            pred_total = self._predict_total_cycle_ewma(t_in)
        else:
            pred_total = self._predict_total_cycle_rules(poste_actuel)

        duree_totale_estimee = pred_total["duree_totale_estimee"]

        # 2. Calcul mathématique du temps restant : ETA = max(5.0, Durée_totale - Temps_écoulé)
        eta_restant = max(5.0, duree_totale_estimee - temps_deja_passe)

        # Si le camion est à l'ensachage ou à la bascule brut, borner par les temps de service résiduels
        if poste_actuel == PosteType.ENSACHAGE:
            eta_restant = max(10.0, min(eta_restant, 45.0))
        elif poste_actuel == PosteType.BASCULE and temps_deja_passe > 30.0:
            eta_restant = max(5.0, min(eta_restant, 20.0))

        return {
            "eta_minutes": round(eta_restant, 1),
            "duree_totale_prevue": round(duree_totale_estimee, 1),
            "temps_deja_passe": round(temps_deja_passe, 1),
            "niveau_actif": self.niveau,
            "methode": pred_total["methode"],
            "confiance": pred_total["confiance"],
            "note": pred_total["note"],
        }

    # ── Palier 0 : Règles métier & seuils configurés ─────────────────────────
    def _predict_total_cycle_rules(self, poste_actuel: PosteType) -> dict:
        etapes = {e.code: e.seuil_minutes for e in self.db.query(EtapeConfig).filter(EtapeConfig.is_active == True).all()}
        seuil_parking = etapes.get("parking", settings.seuil_attente_parking_max)
        seuil_b_tare = etapes.get("bascule_tare", settings.seuil_bascule_max)
        seuil_ensachage = etapes.get("ensachage", settings.seuil_ensachage_max)
        seuil_b_brut = etapes.get("bascule_brut", 10)
        seuil_porte_sortie = etapes.get("porte_sortie", 10)

        total_prevu = float(seuil_parking + seuil_b_tare + seuil_ensachage + seuil_b_brut + seuil_porte_sortie)
        return {
            "duree_totale_estimee": total_prevu,
            "methode": "regles_metier_dynamiques",
            "confiance": "faible",
            "note": "Règles expertes sur seuils d'usine (EtapeConfig)",
        }

    # ── Palier 1 : Moyenne Mobile Pondérée (EWMA) ────────────────────────────
    def _predict_total_cycle_ewma(self, t_in: datetime) -> dict:
        depuis = t_in - timedelta(days=7)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE,
            Cycle.duree_total.isnot(None),
            Cycle.est_anomalie == False
        ).all()

        if len(cycles) < 10:
            return self._predict_total_cycle_rules(PosteType.PORTE_USINE)

        durees = [float(c.duree_total) for c in cycles]
        s = pd.Series(durees)
        ewma_total = float(s.ewm(span=10).mean().iloc[-1])

        return {
            "duree_totale_estimee": ewma_total,
            "methode": "ewma_adaptatif",
            "confiance": "moyenne",
            "note": f"Moyenne mobile adaptative sur {len(cycles)} cycles récents",
        }

    # ── Palier 2 : Modèles ML (Prophet Champion & XGBoost Challenger) ─────────
    def _predict_total_cycle_ml(self, t_in: datetime, modele_prefere: str) -> dict:
        if modele_prefere == "xgboost":
            res_xgb = self._predict_xgboost(t_in)
            if res_xgb:
                return res_xgb
        return self._predict_prophet(t_in)

    def _predict_prophet(self, t_in: datetime) -> dict:
        model_path = os.path.join(self.MODEL_DIR, "prophet_champion.pkl")
        if not os.path.exists(model_path):
            return self._predict_total_cycle_ewma(t_in)

        try:
            with open(model_path, 'rb') as f:
                artifact = pickle.load(f)
            model = artifact.get('model', artifact)

            future = pd.DataFrame({'ds': [t_in]})
            forecast = model.predict(future)
            yhat = float(forecast['yhat'].iloc[0])
            total_estime = max(30.0, yhat)

            mae = artifact.get('mae', None)
            mae_info = f" (MAE test={mae:.1f}min sur {artifact.get('n_samples',0)} cycles)" if mae else ""
            return {
                "duree_totale_estimee": total_estime,
                "methode": "prophet_production",
                "confiance": "modele_valide",
                "note": f"Forecast Prophet saisonnier{mae_info}. Note : ETA = durée_totale_prévue - temps_écoulé (non conditionné au poste actuel).",
            }
        except Exception as e:
            print(f"[Prediction] Inférence Prophet en échec : {e}")
            return self._predict_total_cycle_ewma(t_in)

    def _predict_xgboost(self, t_in: datetime) -> Optional[dict]:
        model_path = os.path.join(self.MODEL_DIR, "xgboost_champion.pkl")
        if not os.path.exists(model_path):
            return None

        try:
            import xgboost as xgb
            with open(model_path, 'rb') as f:
                artifact = pickle.load(f)
            model = artifact.get('model')
            if not model:
                return None

            # Récupérer les durées des derniers cycles terminés pour les lags causaux
            recents = self.db.query(Cycle.duree_total).filter(
                Cycle.status == TruckStatus.TERMINE,
                Cycle.duree_total.isnot(None),
                Cycle.est_anomalie == False,
                Cycle.entree_porte <= t_in
            ).order_by(Cycle.entree_porte.desc()).limit(10).all()

            recent_durations = [float(r[0]) for r in reversed(recents)] if recents else []
            train_median = float(artifact.get('train_median_imputed', 90.0))

            # Inférence avec le vecteur unifié EXACT (13 colonnes)
            df_vector = build_single_inference_vector(t_in, recent_durations, train_median_y=train_median)
            dmatrix = xgb.DMatrix(df_vector)
            yhat = float(model.predict(dmatrix)[0])
            total_estime = max(30.0, yhat)

            mae = artifact.get('mae', None)
            mae_info = f" (MAE test={mae:.1f}min sur {artifact.get('n_samples',0)} cycles)" if mae else ""
            return {
                "duree_totale_estimee": total_estime,
                "methode": "xgboost_challenger",
                "confiance": "modele_valide",
                "note": f"Forecast XGBoost temporel{mae_info}. Note : ETA = durée_totale_prévue - temps_écoulé (non conditionné au poste actuel).",
            }
        except Exception as e:
            print(f"[Prediction] Inférence XGBoost en échec : {e}")
            return None

    def predict(self, poste_actuel: PosteType, est_tare: bool = True, modele_prefere: str = "prophet") -> dict:
        """Compatibilité avec l'ancienne signature."""
        return self.predict_remaining_eta(poste_actuel, datetime.utcnow(), modele_prefere)
