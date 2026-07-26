"""
Détection d'anomalies par Z-score dynamique.
Identifie les camions qui dépassent significativement la norme.
"""
import numpy as np
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models import Cycle, TruckStatus
from app.config import get_settings

settings = get_settings()


class AnomalyDetector:
    """Détecteur d'anomalies — Z-score > 2 = anomalie."""

    def __init__(self, db: Session):
        self.db = db

    def detecter_anomalies_cycle(self, truck_id: int) -> dict:
        depuis = datetime.utcnow() - timedelta(days=14)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE
        ).all()

        if len(cycles) < 5:
            return self._check_seuils_metier(truck_id)

        durees = np.array([c.duree_total for c in cycles])
        moyenne, ecart_type = np.mean(durees), np.std(durees)

        cycle_actuel = self.db.query(Cycle).filter(
            Cycle.truck_id == truck_id,
            Cycle.status == TruckStatus.EN_COURS
        ).first()

        if not cycle_actuel:
            return {"anomalie": False, "raison": "Aucun cycle en cours"}

        duree_ecoulee = (datetime.utcnow() - cycle_actuel.entree_porte).total_seconds() / 60
        z_score = (duree_ecoulee - moyenne) / ecart_type if ecart_type > 0 else 0
        est_anomalie = z_score > 2.0 or duree_ecoulee > settings.seuil_cycle_total_max

        return {
            "anomalie": est_anomalie,
            "z_score": round(z_score, 2),
            "duree_ecoulee_min": round(duree_ecoulee, 1),
            "moyenne_historique": round(moyenne, 1),
            "ecart_type": round(ecart_type, 1),
            "niveau": 1,
            "raison": (f"Z-score {z_score:.1f} > 2.0" if z_score > 2.0
                       else f"Seuil métier dépassé") if est_anomalie else "Normal"
        }

    def _check_seuils_metier(self, truck_id: int) -> dict:
        """Fallback Niveau 0 : vérification simple des seuils."""
        cycle = self.db.query(Cycle).filter(
            Cycle.truck_id == truck_id,
            Cycle.status == TruckStatus.EN_COURS
        ).first()

        if not cycle:
            return {"anomalie": False, "raison": "Aucun cycle en cours"}

        duree = (datetime.utcnow() - cycle.entree_porte).total_seconds() / 60
        est_anomalie = duree > settings.seuil_cycle_total_max

        return {
            "anomalie": est_anomalie,
            "duree_ecoulee_min": round(duree, 1),
            "seuil_max": settings.seuil_cycle_total_max,
            "niveau": 0,
            "raison": (f"Seuil {settings.seuil_cycle_total_max}min dépassé"
                       if est_anomalie else "Normal — pas assez d'historique")
        }

    def get_poste_bloquant(self) -> dict:
        """Identifie le poste avec la durée moyenne la plus élevée."""
        depuis = datetime.utcnow() - timedelta(days=7)
        cycles = self.db.query(Cycle).filter(
            Cycle.entree_porte >= depuis,
            Cycle.status == TruckStatus.TERMINE
        ).all()

        if not cycles:
            return {"poste_bloquant": None, "note": "Pas assez de données"}

        import pandas as pd
        df = pd.DataFrame([{
            'parking': c.duree_parking,
            'bascule': c.duree_bascule_tare + c.duree_bascule_brut,
            'ensachage': c.duree_ensachage
        } for c in cycles])

        moyennes = df.mean().to_dict()
        bloquant = max(moyennes, key=moyennes.get)

        return {
            "poste_bloquant": bloquant,
            "duree_moyenne_min": round(moyennes[bloquant], 1),
            "details": {k: round(v, 1) for k, v in moyennes.items()}
        }
