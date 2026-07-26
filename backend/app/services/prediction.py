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
        """Règles métier — fonctionne sans aucune donnée."""
        temps = 0.0
        if poste_actuel == PosteType.PORTE_USINE:
            temps = (settings.seuil_attente_parking_max + settings.seuil_bascule_max +
                     settings.seuil_ensachage_max + settings.seuil_bascule_max + 10)
        elif poste_actuel == PosteType.PARKING:
            temps = (settings.seuil_bascule_max + settings.seuil_ensachage_max +
                     settings.seuil_bascule_max + 10)
        elif poste_actuel == PosteType.BASCULE:
            temps = (settings.seuil_ensachage_max + settings.seuil_bascule_max + 10
                     if est_tare else 10)
        elif poste_actuel == PosteType.ENSACHAGE:
            temps = settings.seuil_bascule_max + 10

        return {
            "eta_minutes": round(temps, 1),
            "niveau": 0,
            "methode": "regles_metier",
            "confiance": "faible",
            "note": "Basé sur les seuils configurés — aucune donnée historique"
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
        """XGBoost — mode expérimental, pour comparaison A/B uniquement."""
        import pickle
        with open("models/xgboost_champion.pkl", 'rb') as f:
            artifact = pickle.load(f)

        # Simplifié : retourne la prédiction du modèle
        return {
            "eta_minutes": 0.0,  # À implémenter selon feature engineering
            "niveau": 2,
            "methode": "xgboost_experimental",
            "confiance": "moyenne",
            "note": "Mode expérimental — à valider sur données réelles"
        }

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
