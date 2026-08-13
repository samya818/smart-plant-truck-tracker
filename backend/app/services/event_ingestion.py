"""
Service d'ingestion unifié — Caméra fixe + Agent mobile coexistent.
Quelle que soit la source, on aboutit au même Event horodaté.

Mécanismes de robustesse :
  1. DÉDUPLICATION        : camera + agent dans les 30s → source="hybrid"
  2. AUTO-FERMETURE       : nouvelle entrée porte → ancien cycle EN_COURS fermé avec gap
  3. INFÉRENCE SORTIE     : sortie sans entrée → entrée inférée créée automatiquement
  4. WATCHDOG             : cycle EN_COURS > seuil_total → status EXPIRE
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import (
    Event, Truck, Cycle, PosteType, PosteConfig,
    CaptureMode, DelayCause, TruckStatus
)
from app.cache import cache_invalidate

# ─── Constantes ─────────────────────────────────────────────────────────────
GAP_ROUTE_MINUTES = 3        # Temps minimal entre sortie inférée et nouvelle entrée
WATCHDOG_SEUIL_HOURS = 8     # Au-delà de 8h EN_COURS → EXPIRE


class EventIngestionService:
    """Point d'entrée unique pour TOUT événement (caméra ou agent)."""

    def __init__(self, db: Session):
        self.db = db

    # ════════════════════════════════════════════════════════════════════════
    # ENTRÉE PRINCIPALE
    # ════════════════════════════════════════════════════════════════════════
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
        Crée un événement de manière robuste.
        Gère automatiquement les cycles incomplets.
        """
        truck = self._get_or_create_truck(plaque)
        now = horodatage or datetime.utcnow()
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)

        # ── Vérif poste actif ───────────────────────────────────────────────
        config = self.db.query(PosteConfig).filter(PosteConfig.poste == poste).first()
        if config and not config.is_active:
            raise ValueError(f"Poste {poste.value} désactivé")

        # ── 1. DÉDUPLICATION (camera + agent dans les 30s) ──────────────────
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

        # ── 2. AUTO-FERMETURE cycle précédent si nouvelle entrée porte ──────
        if poste == PosteType.PORTE_USINE and type_event == "entree":
            self._auto_close_stale_cycle(truck.id, new_entry_time=now)

        # ── 3. INFÉRENCE SORTIE → ENTRÉE manquante ──────────────────────────
        if type_event == "sortie" and poste != PosteType.PORTE_USINE:
            self._infer_missing_entry(truck.id, poste, now, source)

        # ── Seuil de confiance OCR fallback ( < 0.65 nécessite confirmation ) ──
        necesita_confirmacion = bool(confiance_ocr is not None and confiance_ocr < 0.65)

        # ── Création de l'événement ──────────────────────────────────────────
        event = Event(
            truck_id=truck.id,
            poste=poste,
            type_event=type_event,
            horodatage=now,
            source=source,
            agent_id=agent_id,
            image_path=image_path,
            confiance_ocr=confiance_ocr,
            necesita_confirmacion=necesita_confirmacion,
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

        # ── Diffusion temps réel WebSocket ───────────────────────────────────
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
                pass
        except Exception:
            pass

        # ── Invalidation cache Redis ───────────────────────────────────────
        cache_invalidate("dashboard:*")
        cache_invalidate("analytics:*")

        return event

    # ════════════════════════════════════════════════════════════════════════
    # MÉCANISME 2 — AUTO-FERMETURE DU CYCLE PRÉCÉDENT
    # ════════════════════════════════════════════════════════════════════════
    def _auto_close_stale_cycle(self, truck_id: int, new_entry_time: datetime):
        """
        Si ce camion a un cycle EN_COURS et qu'une nouvelle entrée porte arrive,
        on infère qu'il est sorti avant cette nouvelle entrée.
        On ferme l'ancien cycle avec : sortie_inférée = new_entry_time - GAP_ROUTE_MINUTES.
        """
        stale = self.db.query(Cycle).filter(
            Cycle.truck_id == truck_id,
            Cycle.status == TruckStatus.EN_COURS
        ).order_by(Cycle.entree_porte.desc()).first()

        if not stale:
            return

        # Sortie inférée = nouvelle entrée - gap route (au minimum 1 min après l'entrée du cycle)
        inferred_sortie = new_entry_time - timedelta(minutes=GAP_ROUTE_MINUTES)
        entree = stale.entree_porte
        if entree.tzinfo:
            entree = entree.replace(tzinfo=None)

        # Sécurité : la sortie inférée ne peut pas être avant l'entrée
        if inferred_sortie <= entree:
            inferred_sortie = entree + timedelta(minutes=1)

        stale.sortie_porte  = inferred_sortie
        stale.status        = TruckStatus.TERMINE
        stale.auto_closed   = True
        stale.gap_applique  = GAP_ROUTE_MINUTES
        stale.est_anomalie  = True    # signalé mais proprement fermé

        self._recalculate_durations(stale)
        self.db.commit()

    # ════════════════════════════════════════════════════════════════════════
    # MÉCANISME 3 — INFÉRER L'ENTRÉE MANQUANTE (poste intermédiaire)
    # ════════════════════════════════════════════════════════════════════════
    def _infer_missing_entry(
        self, truck_id: int, poste: PosteType, sortie_time: datetime, source: str
    ):
        """
        Si une sortie d'un poste intermédiaire arrive sans entrée correspondante
        dans le même cycle, on crée une entrée inférée 1 minute avant la sortie.
        """
        cycle = self.db.query(Cycle).filter(
            Cycle.truck_id == truck_id,
            Cycle.status == TruckStatus.EN_COURS
        ).order_by(Cycle.entree_porte.desc()).first()

        if not cycle:
            return  # Pas de cycle ouvert → rien à inférer

        entree_porte = cycle.entree_porte
        if entree_porte.tzinfo:
            entree_porte = entree_porte.replace(tzinfo=None)

        # Chercher si une entrée pour ce poste existe déjà dans ce cycle
        existing_entry = self.db.query(Event).filter(
            Event.truck_id == truck_id,
            Event.poste == poste,
            Event.type_event == "entree",
            Event.horodatage >= entree_porte
        ).first()

        if existing_entry:
            return  # Entrée déjà présente → pas besoin d'inférer

        # Créer l'entrée inférée 1 minute avant la sortie déclarée
        inferred_entry = Event(
            truck_id=truck_id,
            poste=poste,
            type_event="entree",
            horodatage=sortie_time - timedelta(minutes=1),
            source="inferred",
            agent_id="SYSTEM_INFERRED",
        )
        self.db.add(inferred_entry)
        self.db.commit()

    # ════════════════════════════════════════════════════════════════════════
    # MÉCANISME 4 — WATCHDOG : marquer EXPIRE les cycles trop vieux
    # ════════════════════════════════════════════════════════════════════════
    @staticmethod
    def run_watchdog(db: Session) -> int:
        """
        À appeler périodiquement (ex: toutes les heures via APScheduler).
        Marque EXPIRE tout cycle EN_COURS depuis plus de WATCHDOG_SEUIL_HOURS heures.
        Retourne le nombre de cycles marqués.
        """
        cutoff = datetime.utcnow() - timedelta(hours=WATCHDOG_SEUIL_HOURS)
        stale_cycles = db.query(Cycle).filter(
            Cycle.status == TruckStatus.EN_COURS,
            Cycle.entree_porte <= cutoff
        ).all()

        count = 0
        for cycle in stale_cycles:
            cycle.status     = TruckStatus.EXPIRE
            cycle.est_anomalie = True
            count += 1

        if count:
            db.commit()
        return count

    # ════════════════════════════════════════════════════════════════════════
    # ENDPOINT ANOMALIES (appelé par le dashboard)
    # ════════════════════════════════════════════════════════════════════════
    @staticmethod
    def get_anomalies(db: Session) -> dict:
        """
        Retourne un rapport complet des situations anormales :
        - Cycles EN_COURS anciens (> 4h)
        - Cycles auto-fermés
        - Cycles EXPIRE
        """
        now = datetime.utcnow()
        warning_cutoff = now - timedelta(hours=4)

        en_cours_vieux = db.query(Cycle).filter(
            Cycle.status == TruckStatus.EN_COURS,
            Cycle.entree_porte <= warning_cutoff
        ).order_by(Cycle.entree_porte.asc()).all()

        auto_closes = db.query(Cycle).filter(
            Cycle.auto_closed == True
        ).order_by(Cycle.entree_porte.desc()).limit(20).all()

        expires = db.query(Cycle).filter(
            Cycle.status == TruckStatus.EXPIRE
        ).order_by(Cycle.entree_porte.desc()).limit(20).all()

        def fmt(c: Cycle) -> dict:
            ep = c.entree_porte
            if ep and ep.tzinfo:
                ep = ep.replace(tzinfo=None)
            duree_h = round((now - ep).total_seconds() / 3600, 1) if ep else None
            return {
                "cycle_id": c.id,
                "immatriculation": c.truck.immatriculation if c.truck else "?",
                "entree_porte": ep.isoformat() if ep else None,
                "sortie_porte": c.sortie_porte.isoformat() if c.sortie_porte else None,
                "status": c.status.value,
                "duree_heures": duree_h,
                "auto_closed": c.auto_closed,
                "gap_applique": c.gap_applique,
            }

        return {
            "en_cours_vieux": [fmt(c) for c in en_cours_vieux],
            "auto_fermes":    [fmt(c) for c in auto_closes],
            "expires":        [fmt(c) for c in expires],
            "total_alertes":  len(en_cours_vieux) + len(expires),
        }

    # ════════════════════════════════════════════════════════════════════════
    # HELPERS PRIVÉS
    # ════════════════════════════════════════════════════════════════════════
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
            else:
                # ── Sortie Porte Usine sans cycle ouvert → créer cycle minimal
                inferred_entry = now - timedelta(minutes=GAP_ROUTE_MINUTES)
                cycle = Cycle(
                    truck_id=truck_id,
                    entree_porte=inferred_entry,
                    sortie_porte=now,
                    status=TruckStatus.TERMINE,
                    auto_closed=True,
                    gap_applique=GAP_ROUTE_MINUTES,
                    est_anomalie=True,
                )
                self.db.add(cycle)
                self.db.commit()

    def _recalculate_durations(self, cycle: Cycle):
        """Recalcule toutes les durées à partir des paires entree/sortie."""
        def make_naive(dt):
            return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt

        # Réinitialiser toutes les durées avant recalcul
        cycle.duree_parking = 0.0
        cycle.duree_bascule_tare = 0.0
        cycle.duree_ensachage = 0.0
        cycle.duree_bascule_brut = 0.0

        entree_porte = make_naive(cycle.entree_porte)
        sortie_porte = make_naive(cycle.sortie_porte)

        events = self.db.query(Event).filter(
            Event.truck_id == cycle.truck_id,
            Event.horodatage >= entree_porte
        ).order_by(Event.horodatage).all()

        poste_times = {}
        for ev in events:
            key = (ev.poste, ev.type_event)
            poste_times[key] = make_naive(ev.horodatage)

        # Parking
        if (PosteType.PARKING, "entree") in poste_times and (PosteType.PARKING, "sortie") in poste_times:
            cycle.duree_parking = (
                poste_times[(PosteType.PARKING, "sortie")] -
                poste_times[(PosteType.PARKING, "entree")]
            ).total_seconds() / 60

        # Bascule — appariement strict des paires (entrée, sortie) séquentielle
        bascule_events = [e for e in events if e.poste == PosteType.BASCULE]
        bascule_pairs = []
        last_entry = None
        for be in bascule_events:
            if be.type_event == "entree":
                last_entry = be
            elif be.type_event == "sortie" and last_entry is not None:
                dur = (make_naive(be.horodatage) - make_naive(last_entry.horodatage)).total_seconds() / 60
                if 0 <= dur <= 60:  # Durée de pesée valide (max 60 min)
                    bascule_pairs.append(dur)
                last_entry = None

        if len(bascule_pairs) >= 1:
            cycle.duree_bascule_tare = round(bascule_pairs[0], 1)
        if len(bascule_pairs) >= 2:
            cycle.duree_bascule_brut = round(bascule_pairs[1], 1)

        # Ensachage
        if (PosteType.ENSACHAGE, "entree") in poste_times and (PosteType.ENSACHAGE, "sortie") in poste_times:
            cycle.duree_ensachage = (
                poste_times[(PosteType.ENSACHAGE, "sortie")] -
                poste_times[(PosteType.ENSACHAGE, "entree")]
            ).total_seconds() / 60

        # Durée totale
        if sortie_porte and entree_porte:
            cycle.duree_total = (sortie_porte - entree_porte).total_seconds() / 60
