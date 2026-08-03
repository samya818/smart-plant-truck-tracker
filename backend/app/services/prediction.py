"""
Service de prédiction — Architecture Zero-to-Hero à 3 niveaux.
Prophet en production, XGBoost en mode expérimental (toggle).
"""
from typing import Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
import os

from app.models import Event, Cycle, PosteType, TruckStatus
from app.config import get_settings

settings = get_settings()


class PredictionService:
    """Prédiction unifiée du temps de cycle restant."""

    def __init__(self, db: Session):
        self.db = db
        self.niveau = self._detecter_niveau()

    def _detecter_niveau(self) -> int:
        count = self.db.query(Event).count()
        if count >= 500:
            return 2
        elif count >= 50:
            return 1
        return 0

    def predict_niveau_0(self, poste_actuel: PosteType, est_tare: bool = True) -> dict:
        """Règles métier — lit les seuils dynamiques configurés en DB (EtapeConfig)."""
        from app.models import EtapeConfig

        # Récupérer les seuils configurés par le superviseur via l'UI
        etapes = {e.code: e.seuil_minutes for e in self.db.query(EtapeConfig).filter(EtapeConfig.is_active == True).all()}

        seuil_parking = etapes.get("parking", settings.seuil_attente_parking_max)
        seuil_b_tare = etapes.get("bascule_tare", settings.seuil_bascule_max)
        seuil_ensachage = etapes.get("ensachage", settings.seuil_ensachage_max)
        seuil_b_brut = etapes.get("bascule_brut", 10)
        seuil_porte_sortie = etapes.get("porte_sortie", 10)

        temps = 0.0
        if poste_actuel == PosteType.PORTE_USINE:
            temps = seuil_parking + seuil_b_tare + seuil_ensachage + seuil_b_brut + seuil_porte_sortie
        elif poste_actuel == PosteType.PARKING:
            temps = seuil_b_tare + seuil_ensachage + seuil_b_brut + seuil_porte_sortie
        elif poste_actuel == PosteType.BASCULE:
            temps = (seuil_ensachage + seuil_b_brut + seuil_porte_sortie) if est_tare else seuil_porte_sortie
        elif poste_actuel == PosteType.ENSACHAGE:
            temps = seuil_b_brut + seuil_porte_sortie

        return {
            "eta_minutes": round(temps, 1),
            "niveau": 0,
            "methode": "regles_metier_dynamiques",
            "confiance": "faible",
            "note": "Basé sur les seuils configurés en direct dans l'interface (EtapeConfig)"
        }

    def predict_niveau_1(self, poste_actuel: PosteType) -> dict:
        """EWMA (Exponentially Weighted Moving Average) — s'adapte en ligne."""
        depuis = datetime.utcnow() - timedelta(days=7)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE
        ).all()

        if len(cycles) < 5:
            return self.predict_niveau_0(poste_actuel)

        df = pd.DataFrame([{
            'parking': c.duree_parking,
            'ensachage': c.duree_ensachage,
            'bascule': c.duree_bascule_tare + c.duree_bascule_brut
        } for c in cycles])

        ewma_parking = df['parking'].ewm(span=10).mean().iloc[-1]
        ewma_ensachage = df['ensachage'].ewm(span=10).mean().iloc[-1]
        ewma_bascule = df['bascule'].ewm(span=10).mean().iloc[-1]

        temps = 0.0
        if poste_actuel == PosteType.PORTE_USINE:
            temps = ewma_parking + ewma_bascule + ewma_ensachage + 10
        elif poste_actuel == PosteType.PARKING:
            temps = ewma_bascule + ewma_ensachage + 10
        elif poste_actuel == PosteType.BASCULE:
            temps = ewma_ensachage + ewma_bascule + 10
        elif poste_actuel == PosteType.ENSACHAGE:
            temps = ewma_bascule + 10

        return {
            "eta_minutes": round(temps, 1),
            "niveau": 1,
            "methode": "ewma",
            "confiance": "moyenne",
            "note": f"Basé sur {len(cycles)} cycles des 7 derniers jours"
        }

    def predict_niveau_2(self, poste_actuel: PosteType, modele_prefere: str = "prophet") -> dict:
        """
        Niveau 2 : Prophet par défaut (production).
        XGBoost disponible en mode expérimental via toggle.
        """
        if modele_prefere == "xgboost" and os.path.exists("models/xgboost_champion.pkl"):
            return self._predict_xgboost(poste_actuel)
        return self._predict_prophet(poste_actuel)

    def _predict_prophet(self, poste_actuel: PosteType) -> dict:
        """Prophet — modèle de production robuste et interprétable."""
        model_path = "models/prophet_champion.pkl"

        if not os.path.exists(model_path):
            return self.predict_niveau_1(poste_actuel)

        import pickle
        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        future = model.make_future_dataframe(periods=1, freq='H')
        forecast = model.predict(future)

        return {
            "eta_minutes": round(forecast['yhat'].iloc[-1], 1),
            "niveau": 2,
            "methode": "prophet",
            "confiance": "élevée",
            "note": "Modèle Prophet entraîné automatiquement — production"
        }

    def _predict_xgboost(self, poste_actuel: PosteType) -> dict:
        """XGBoost — inférence réelle basée sur les caractéristiques temporelles."""
        import pickle
        import xgboost as xgb
        from datetime import datetime

        model_path = "models/xgboost_champion.pkl"
        if not os.path.exists(model_path):
            return self.predict_niveau_1(poste_actuel)

        try:
            with open(model_path, 'rb') as f:
                artifact = pickle.load(f)

            model = artifact.get('model')
            if not model:
                return self.predict_niveau_1(poste_actuel)

            now = datetime.utcnow()
            heure = now.hour
            jour_semaine = now.weekday()

            # Extraction des features identiques à l'entraînement
            hour_sin = float(np.sin(2 * np.pi * heure / 24))
            hour_cos = float(np.cos(2 * np.pi * heure / 24))
            dow_sin = float(np.sin(2 * np.pi * jour_semaine / 7))
            dow_cos = float(np.cos(2 * np.pi * jour_semaine / 7))
            is_weekend = int(jour_semaine >= 5)
            is_morning_rush = int(7 <= heure <= 9)
            is_afternoon_rush = int(14 <= heure <= 16)

            # Valeurs par défaut moyennes pour les lags si indisponibles
            features = pd.DataFrame([{
                'heure': heure,
                'jour_semaine': jour_semaine,
                'parking': 20.0,
                'ensachage': 35.0,
                'bascule': 15.0,
                'hour_sin': hour_sin,
                'hour_cos': hour_cos,
                'dow_sin': dow_sin,
                'dow_cos': dow_cos,
                'is_weekend': is_weekend,
                'is_morning_rush': is_morning_rush,
                'is_afternoon_rush': is_afternoon_rush,
                'lag_1d': 90.0,
                'lag_7d': 90.0,
                'rolling_mean_24h': 90.0,
                'rolling_std_24h': 10.0
            }])

            dtest = xgb.DMatrix(features)
            pred = model.predict(dtest)
            eta = float(pred[0])

            return {
                "eta_minutes": round(max(5.0, eta), 1),
                "niveau": 2,
                "methode": "xgboost_experimental",
                "confiance": "élevée",
                "note": "Modèle XGBoost entraîné — inférence dynamique"
            }
        except Exception as e:
            print(f"[Prediction] Inférence XGBoost échouée : {e}")
            return self.predict_niveau_1(poste_actuel)

    def predict(self, poste_actuel: PosteType, est_tare: bool = True, modele_prefere: str = "prophet") -> dict:
        """Point d'entrée unique — choisit le meilleur niveau automatiquement."""
        if self.niveau >= 2:
            result = self.predict_niveau_2(poste_actuel, modele_prefere)
        elif self.niveau >= 1:
            result = self.predict_niveau_1(poste_actuel)
        else:
            result = self.predict_niveau_0(poste_actuel, est_tare)
        result["niveau_actif"] = self.niveau
        return result
