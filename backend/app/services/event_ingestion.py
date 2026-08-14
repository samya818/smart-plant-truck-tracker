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

# ──────────────────────────────────────────────────────────────────────────────
# AUTOMATE D'ÉTATS FINI DU CYCLE CAMION (FSM Industrielle)
# ──────────────────────────────────────────────────────────────────────────────
# Modélise rigoureusement la séquence d'opérations dans la cimenterie :
# ARRIVED_PORTE -> PARKING_IN -> PARKING_OUT -> TARE_IN -> TARE_OUT
#   -> LOADING_IN -> LOADING_OUT -> GROSS_IN -> GROSS_OUT -> EXITED_PORTE
VALID_FSM_TRANSITIONS: dict[str, list[str]] = {
    "NONE": ["porte_usine:entree"],
    "porte_usine:entree": ["parking:entree", "bascule:entree", "ensachage:entree"],
    "parking:entree": ["parking:sortie"],
    "parking:sortie": ["bascule:entree", "ensachage:entree"],
    "bascule:entree": ["bascule:sortie"],
    "bascule:sortie": ["ensachage:entree", "porte_usine:sortie", "parking:entree"],
    "ensachage:entree": ["ensachage:sortie"],
    "ensachage:sortie": ["bascule:entree", "porte_usine:sortie"],
    "porte_usine:sortie": ["porte_usine:entree"],
}

class CycleStateMachine:
    """Valide et audite les transitions d'état du cycle logistique."""

    @staticmethod
    def validate_transition(last_step: Optional[str], new_poste: PosteType, new_type: str) -> tuple[bool, str]:
        """
        Vérifie si la transition est légale selon la FSM d'usine.
        Retourne (est_valide, message_audit).
        """
        current_key = last_step or "NONE"
        candidate_key = f"{new_poste.value}:{new_type}"

        allowed = VALID_FSM_TRANSITIONS.get(current_key, [])
        if candidate_key in allowed:
            return True, f"Transition FSM valide: {current_key} -> {candidate_key}"

        # Permissivité avec alerte d'anomalie pour non-blocage opérationnel
        return False, f"⚠️ Anomalie de séquence détectée: {current_key} -> {candidate_key} (étape sautée ou inversée)"


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
        gps_accuracy_m: Optional[float] = None,
        delay_cause_id: Optional[int] = None,
        cause_retard_libre: Optional[str] = None,
        minutes_retard: Optional[int] = None,
        horodatage: Optional[datetime] = None,
        client_event_id: Optional[str] = None,
    ) -> Event:
        """
        Crée un événement de manière robuste et idempotente.
        Gère automatiquement les cycles incomplets et les re-jeux offline.
        """
        # ── 0. IDEMPOTENCE STRICTE CLIENT (PWA Offline Queue Replay) ─────────
        if client_event_id:
            existing_event = self.db.query(Event).filter(Event.client_event_id == client_event_id).first()
            if existing_event:
                print(f"[Ingestion] ♻️ Événement idempotent ignoré (déjà existant en DB) : client_event_id={client_event_id}")
                return existing_event

        truck = self._get_or_create_truck(plaque)
        truck_id = truck.id
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
                Event.truck_id == truck_id,
                Event.poste == poste,
                Event.type_event == type_event,
                Event.horodatage >= now - timedelta(seconds=30)
            )
        ).first()

        if recent and (not client_event_id or recent.client_event_id == client_event_id or (source == "agent_mobile" and recent.source == "camera")):
            if source == "agent_mobile" and recent.source == "camera":
                recent.source = "hybrid"
                recent.agent_id = agent_id
                if client_event_id and not recent.client_event_id:
                    recent.client_event_id = client_event_id
                if delay_cause_id:
                    recent.delay_cause_id = delay_cause_id
                self.db.commit()
                self.db.refresh(recent)
            return recent

        # ── 2. AUTO-FERMETURE cycle précédent si nouvelle entrée porte ──────
        if poste == PosteType.PORTE_USINE and type_event == "entree":
            self._auto_close_stale_cycle(truck_id, new_entry_time=now)

        # ── 3. VALIDATION FORMELLE AUTOMATE D'ÉTATS (FSM) ───────────────────
        last_event = self.db.query(Event).filter(Event.truck_id == truck_id).order_by(Event.horodatage.desc()).first()
        last_step_key = f"{last_event.poste.value}:{last_event.type_event}" if last_event else None
        is_valid_transition, fsm_msg = CycleStateMachine.validate_transition(last_step_key, poste, type_event)
        if not is_valid_transition:
            try:
                print(f"[FSM Audit] {plaque} : {fsm_msg}")
            except Exception:
                pass

        # ── 4. INFÉRENCE SORTIE → ENTRÉE manquante ──────────────────────────
        if type_event == "sortie" and poste != PosteType.PORTE_USINE:
            self._infer_missing_entry(truck_id, poste, now, source)

        # ── Seuil de confiance OCR fallback ( < 0.65 nécessite confirmation ) ──
        necesita_confirmacion = bool(confiance_ocr is not None and confiance_ocr < 0.65)

        # ── Création de l'événement ──────────────────────────────────────────
        event = Event(
            client_event_id=client_event_id,
            truck_id=truck_id,
            poste=poste,
            type_event=type_event,
            horodatage=now,                        # occurred_at
            received_at=datetime.utcnow(),         # received_at
            sync_status="synced_offline" if client_event_id else "realtime",
            source=source,
            agent_id=agent_id,
            image_path=image_path,
            confiance_ocr=confiance_ocr,
            necesita_confirmacion=necesita_confirmacion,
            has_fsm_anomaly=not is_valid_transition,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            gps_accuracy_m=gps_accuracy_m,
            delay_cause_id=delay_cause_id,
            cause_retard_libre=cause_retard_libre,
            minutes_retard=minutes_retard,
        )
        # ── Persistance avec gestion atomique des collisions d'idempotence ──
        try:
            self.db.add(event)
            self.db.commit()
            try:
                self.db.refresh(event)
            except Exception:
                # db.refresh() peut échouer dans un contexte SQLite multi-thread
                # (StaticPool partagé). En PostgreSQL, cela n'arrive jamais.
                # On ignore silencieusement : l'événement est déjà committée en DB.
                pass
        except Exception as e:
            self.db.rollback()
            if client_event_id:
                existing = self.db.query(Event).filter(Event.client_event_id == client_event_id).first()
                if existing:
                    try:
                        print(f"[Ingestion] Collision concurrente interceptée avec succès : client_event_id={client_event_id}")
                    except Exception:
                        pass
                    return existing
            raise e

        self._update_cycle(truck_id, poste, type_event, now)

        if not is_valid_transition:
            cycle = self.db.query(Cycle).filter(Cycle.truck_id == truck_id, Cycle.status == TruckStatus.EN_COURS).first()
            if cycle:
                cycle.has_fsm_anomaly = True
                self.db.commit()

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
        inferred_time = sortie_time - timedelta(minutes=1)
        inferred_entry = Event(
            truck_id=truck_id,
            poste=poste,
            type_event="entree",
            horodatage=inferred_time,
            received_at=datetime.utcnow(),
            source=f"inferred_{source}",
            is_inferred=True,
            has_fsm_anomaly=True,
            cause_retard_libre="Entrée inférée automatiquement (capteur manquant)",
        )
        self.db.add(inferred_entry)
        self.db.commit()
        
        cycle.est_anomalie = True
        self.db.commit()
        print(f"[Ingestion] ⚙️ Entrée inférée créée (is_inferred=True) : truck_id={truck_id} @ {poste.value} à {inferred_time.strftime('%H:%M:%S')}")

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
        """
        Recalcule toutes les durées à partir des paires entree/sortie.

        Isolation temporelle stricte : seuls les événements dans
        [entree_porte, sortie_porte] sont considérés pour éviter que les
        événements d'un cycle futur du même camion contaminent ce cycle.

        Pour les cycles encore ouverts (sortie_porte=None), on utilise now()
        comme borne supérieure — ce qui est conservateur mais jamais erroné.

        Appariement séquentiel généralisé : parking, ensachage et bascule
        utilisent tous la même logique entree→sortie pour supporter plusieurs
        passages au même poste dans un seul cycle.
        """
        def make_naive(dt):
            return dt.replace(tzinfo=None) if dt and dt.tzinfo else dt

        # Réinitialiser toutes les durées avant recalcul
        cycle.duree_parking = 0.0
        cycle.duree_bascule_tare = 0.0
        cycle.duree_ensachage = 0.0
        cycle.duree_bascule_brut = 0.0

        entree_porte = make_naive(cycle.entree_porte)
        sortie_porte = make_naive(cycle.sortie_porte)

        # Borne supérieure : sortie_porte si disponible, sinon maintenant
        # (isolation stricte : jamais d'événements hors de la fenêtre de ce cycle)
        upper_bound = sortie_porte if sortie_porte else datetime.utcnow()

        events = self.db.query(Event).filter(
            Event.truck_id == cycle.truck_id,
            Event.horodatage >= entree_porte,
            Event.horodatage <= upper_bound,   # ← CORRECTION CRITIQUE : borne supérieure
        ).order_by(Event.horodatage).all()

        def sequential_pairs(poste_type: PosteType) -> list[float]:
            """
            Appariement séquentiel strict : entree→sortie, entree→sortie, ...
            Retourne la liste des durées (en minutes) de chaque passage.
            Fonctionne pour parking, ensachage, bascule — tous les postes.
            """
            pairs = []
            last_entry = None
            for ev in events:
                if ev.poste != poste_type:
                    continue
                t = make_naive(ev.horodatage)
                if ev.type_event == "entree":
                    last_entry = t
                elif ev.type_event == "sortie" and last_entry is not None:
                    dur = (t - last_entry).total_seconds() / 60
                    if 0 <= dur <= 120:  # Durée valide : 0 à 120 min par passage
                        pairs.append(round(dur, 1))
                    last_entry = None
            return pairs

        # Parking : cumul de tous les passages (camion peut faire demi-tour)
        parking_pairs = sequential_pairs(PosteType.PARKING)
        if parking_pairs:
            cycle.duree_parking = round(sum(parking_pairs), 1)

        # Ensachage : cumul de tous les passages (ex : double chargement)
        ensachage_pairs = sequential_pairs(PosteType.ENSACHAGE)
        if ensachage_pairs:
            cycle.duree_ensachage = round(sum(ensachage_pairs), 1)

        # Bascule — appariement séquentiel : première paire = tare, deuxième = brut
        bascule_pairs = sequential_pairs(PosteType.BASCULE)
        if len(bascule_pairs) >= 1:
            cycle.duree_bascule_tare = bascule_pairs[0]
        if len(bascule_pairs) >= 2:
            cycle.duree_bascule_brut = bascule_pairs[1]

        # Durée totale
        if sortie_porte and entree_porte:
            cycle.duree_total = round((sortie_porte - entree_porte).total_seconds() / 60, 1)
