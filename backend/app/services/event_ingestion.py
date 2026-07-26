"""
Service d'ingestion unifié — Caméra fixe + Agent mobile coexistent.
Quelle que soit la source, on aboutit au même Event horodaté.
Gère la déduplication (caméra + agent dans les 30s → source="hybrid").
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import Event, Truck, Cycle, PosteType, PosteConfig, CaptureMode, DelayCause, TruckStatus


class EventIngestionService:
    """Point d'entrée unique pour TOUT événement (caméra ou agent)."""

    def __init__(self, db: Session):
        self.db = db

    def ingest_event(
        self,
        plaque: str,
        poste: PosteType,
        type_event: Literal["entree", "sortie"],
        source: Literal["camera", "agent_mobile", "manuel", "simulation"],
        agent_id: Optional[str] = None,
        image_path: Optional[str] = None,
        confiance_ocr: Optional[float] = None,
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
        delay_cause_id: Optional[int] = None,
        cause_retard_libre: Optional[str] = None,
        minutes_retard: Optional[int] = None,
        horodatage: Optional[datetime] = None,
    ) -> Event:
        """
        Crée un événement de manière idempotente.
        Dédoublonnage : si événement identique dans les 30 dernières secondes,
        on fusionne (source devient "hybrid").
        """
        truck = self._get_or_create_truck(plaque)
        now = horodatage or datetime.utcnow()

        config = self.db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
        if config and not config.is_active:
            raise ValueError(f"Poste {poste.value} désactivé")

        # DÉDUPLICATION — éviter doublon caméra + agent
        recent = self.db.query(Event).filter(
            and_(
                Event.truck_id == truck.id,
                Event.poste == poste,
                Event.type_event == type_event,
                Event.horodatage >= now - timedelta(seconds=30)
            )
        ).first()

        if recent:
            if source == "agent_mobile" and recent.source == "camera":
                recent.source = "hybrid"
                recent.agent_id = agent_id
                if delay_cause_id:
                    recent.delay_cause_id = delay_cause_id
                self.db.commit()
                self.db.refresh(recent)
            return recent

        event = Event(
            truck_id=truck.id,
            poste=poste,
            type_event=type_event,
            horodatage=now,
            source=source,
            agent_id=agent_id,
            image_path=image_path,
            confiance_ocr=confiance_ocr,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            delay_cause_id=delay_cause_id,
            cause_retard_libre=cause_retard_libre,
            minutes_retard=minutes_retard,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        self._update_cycle(truck.id, poste, type_event, now)

        if delay_cause_id:
            cause = self.db.query(DelayCause).get(delay_cause_id)
            if cause:
                cause.usage_count += 1
                self.db.commit()

        # --- DIFFUSION TEMPS RÉEL VIA WEBSOCKET ---
        try:
            import asyncio
            from app.main import manager
            payload = {
                "type": "NEW_EVENT",
                "poste": poste.value,
                "type_event": type_event,
                "immatriculation": plaque.upper()
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast(payload))
            except RuntimeError:
                # Pas de boucle d'événement active (ex: script init_db.py)
                pass
        except ImportError:
            pass

        return event

    def _get_or_create_truck(self, plaque: str) -> Truck:
        truck = self.db.query(Truck).filter(Truck.immatriculation == plaque).first()
        if not truck:
            truck = Truck(immatriculation=plaque.upper().strip())
            self.db.add(truck)
            self.db.commit()
            self.db.refresh(truck)
        return truck

    def _update_cycle(self, truck_id: int, poste: PosteType, type_event: str, now: datetime):
        if poste == PosteType.PORTE_USINE and type_event == "entree":
            cycle = Cycle(truck_id=truck_id, entree_porte=now, status=TruckStatus.EN_COURS)
            self.db.add(cycle)
            self.db.commit()

        elif poste == PosteType.PORTE_USINE and type_event == "sortie":
            cycle = self.db.query(Cycle).filter(
                Cycle.truck_id == truck_id,
                Cycle.status == TruckStatus.EN_COURS
            ).order_by(Cycle.entree_porte.desc()).first()
            if cycle:
                cycle.sortie_porte = now
                cycle.status = TruckStatus.TERMINE
                self._recalculate_durations(cycle)
                self.db.commit()

    def _recalculate_durations(self, cycle: Cycle):
        """Recalcule toutes les durées à partir des paires entree/sortie."""
        events = self.db.query(Event).filter(
            Event.truck_id == cycle.truck_id,
            Event.horodatage >= cycle.entree_porte
        ).order_by(Event.horodatage).all()

        poste_times = {}
        for ev in events:
            key = (ev.poste, ev.type_event)
            poste_times[key] = ev.horodatage

        # Parking
        if (PosteType.PARKING, "entree") in poste_times and (PosteType.PARKING, "sortie") in poste_times:
            cycle.duree_parking = (poste_times[(PosteType.PARKING, "sortie")] - poste_times[(PosteType.PARKING, "entree")]).total_seconds() / 60

        # Bascule tare (1er passage)
        bascule_entries = [e for e in events if e.poste == PosteType.BASCULE and e.type_event == "entree"]
        bascule_exits = [e for e in events if e.poste == PosteType.BASCULE and e.type_event == "sortie"]
        if len(bascule_entries) >= 1 and len(bascule_exits) >= 1:
            cycle.duree_bascule_tare = (bascule_exits[0].horodatage - bascule_entries[0].horodatage).total_seconds() / 60
        if len(bascule_entries) >= 2 and len(bascule_exits) >= 2:
            cycle.duree_bascule_brut = (bascule_exits[1].horodatage - bascule_entries[1].horodatage).total_seconds() / 60

        # Ensachage
        if (PosteType.ENSACHAGE, "entree") in poste_times and (PosteType.ENSACHAGE, "sortie") in poste_times:
            cycle.duree_ensachage = (poste_times[(PosteType.ENSACHAGE, "sortie")] - poste_times[(PosteType.ENSACHAGE, "entree")]).total_seconds() / 60

        if cycle.sortie_porte and cycle.entree_porte:
            cycle.duree_total = (cycle.sortie_porte - cycle.entree_porte).total_seconds() / 60
