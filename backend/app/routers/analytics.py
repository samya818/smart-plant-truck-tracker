"""Router API pour les analyses historiques et prédictions."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
import statistics

from app.database import get_db
from app.models import Cycle, Event, DelayCause, Truck, Transporteur, TruckStatus, PosteType
from app.schemas import CycleRead
from app.config import get_settings

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
settings = get_settings()


@router.get("/cycles", response_model=List[CycleRead])
def list_cycles(db: Session = Depends(get_db)):
    """Retourne l'historique des cycles de camions avec eager loading."""
    return db.query(Cycle).options(joinedload(Cycle.truck)).order_by(Cycle.entree_porte.desc()).limit(100).all()


from app.cache import cache_get, cache_set

@router.get("/durees-moyennes")
def get_durees_moyennes(db: Session = Depends(get_db)):
    """Durées moyennes par étape (sur 30 jours). Mise en cache Redis (TTL 60s)."""
    cache_key = "analytics:durees_moyennes"
    cached = cache_get(cache_key)
    if cached:
        return cached

    depuis = datetime.utcnow() - timedelta(days=30)
    # Filtre uniquement les cycles réalistes (duree_total >= 10 min, non anomalie)
    # pour ne pas polluer les moyennes avec des cycles inférés ou auto-fermés
    cycles = db.query(Cycle).filter(
        Cycle.status == TruckStatus.TERMINE,
        Cycle.entree_porte >= depuis,
        Cycle.duree_total >= 10.0,
        Cycle.est_anomalie == False  # noqa: E712 — SQLAlchemy ne supporte pas `is False`
    ).all()

    if len(cycles) < 10:
        # Valeurs réalistes de référence usine si peu de données historiques
        res = {
            "parking":        {"moyenne": 20.0, "nb_cycles": len(cycles)},
            "bascule_tare":   {"moyenne": 10.0, "nb_cycles": len(cycles)},
            "ensachage":      {"moyenne": 35.0, "nb_cycles": len(cycles)},
            "bascule_brut":   {"moyenne": 10.0, "nb_cycles": len(cycles)},
            "porte_sortie":   {"moyenne": 5.0,  "nb_cycles": len(cycles)},
            "nb_cycles_total": len(cycles),
            "source": "valeurs_de_reference_usine"
        }
        cache_set(cache_key, res, ttl=60)
        return res

    def avg(lst, default_val=10.0):
        vals = [v for v in lst if v and v >= 1.0]
        return round(sum(vals) / len(vals), 1) if vals else default_val

    res = {
        "parking":        {"moyenne": avg([c.duree_parking for c in cycles], 20.0),      "nb_cycles": len(cycles)},
        "bascule_tare":   {"moyenne": avg([c.duree_bascule_tare for c in cycles], 10.0), "nb_cycles": len(cycles)},
        "ensachage":      {"moyenne": avg([c.duree_ensachage for c in cycles], 35.0),    "nb_cycles": len(cycles)},
        "bascule_brut":   {"moyenne": avg([c.duree_bascule_brut for c in cycles], 10.0), "nb_cycles": len(cycles)},
        "porte_sortie":   {"moyenne": 5.0,                                               "nb_cycles": len(cycles)},
        "nb_cycles_total": len(cycles),
        "source": "historique_30j"
    }
    cache_set(cache_key, res, ttl=60)
    return res


@router.get("/stats-retards-services")
def get_stats_retards_services(db: Session = Depends(get_db)):
    """
    Statistiques des retards par service / zone :
    Décomposition sur les 4 étapes principales (Parking, Bascule Tare, Ensachage, Bascule Brut)
    avec calcul des dépassements en minutes et du taux de retards.
    """
    depuis = datetime.utcnow() - timedelta(days=30)
    cycles = db.query(Cycle).filter(
        Cycle.status == TruckStatus.TERMINE,
        Cycle.entree_porte >= depuis
    ).all()

    nb_total = len(cycles) or 1

    def avg(lst):
        vals = [v for v in lst if v and v > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    def count_retards(lst, seuil):
        return len([v for v in lst if v and v > seuil])

    # Calculs par étape
    avg_parking = avg([c.duree_parking for c in cycles]) or 15.0
    retards_parking = count_retards([c.duree_parking for c in cycles], settings.seuil_attente_parking_max)

    avg_b_tare = avg([c.duree_bascule_tare for c in cycles]) or 10.0
    retards_b_tare = count_retards([c.duree_bascule_tare for c in cycles], settings.seuil_bascule_max)

    avg_ensachage = avg([c.duree_ensachage for c in cycles]) or 45.0
    retards_ensachage = count_retards([c.duree_ensachage for c in cycles], settings.seuil_ensachage_max)

    avg_b_brut = avg([c.duree_bascule_brut for c in cycles]) or 10.0
    retards_b_brut = count_retards([c.duree_bascule_brut for c in cycles], settings.seuil_bascule_max)

    # Dépassements moyens (en minutes par camion)
    dep_parking = max(0.0, avg_parking - settings.seuil_attente_parking_max)
    dep_b_tare = max(0.0, avg_b_tare - settings.seuil_bascule_max)
    dep_ensachage = max(0.0, avg_ensachage - settings.seuil_ensachage_max)
    dep_b_brut = max(0.0, avg_b_brut - settings.seuil_bascule_max)

    # Causes déclarées par poste
    events_retard = db.query(
        Event.poste,
        DelayCause.nom,
        func.count(Event.id).label("count"),
        func.sum(Event.minutes_retard).label("total_minutes")
    ).join(DelayCause, Event.delay_cause_id == DelayCause.id).filter(
        Event.horodatage >= depuis
    ).group_by(Event.poste, DelayCause.nom).all()

    causes_par_poste = {}
    for poste, cause_nom, count, total_mins in events_retard:
        p_name = poste.value if hasattr(poste, "value") else str(poste)
        if p_name not in causes_par_poste:
            causes_par_poste[p_name] = []
        causes_par_poste[p_name].append({
            "cause": cause_nom,
            "occurrences": count,
            "total_minutes": total_mins or 0
        })

    zones = [
        {
            "key": "parking",
            "etape": "Étape ②",
            "nom": "Parking Usine",
            "action": "Attente avant pesage",
            # (a) Temps moyen réel passé au parking par camion (b) Formule: sum(duree_parking) / nb_cycles
            "temps_moyen": avg_parking,
            # (a) Seuil maximal toléré configuré (b) Formule: settings.seuil_attente_parking_max
            "seuil_max": settings.seuil_attente_parking_max,
            # (a) Minutes excédentaires moyennes par camion (b) Formule: max(0, temps_moyen - seuil_max)
            "depassement": round(dep_parking, 1),
            # (a) Pourcentage de camions ayant dépassé le seuil au parking (b) Formule: (nb_camions_retard_parking / total_cycles) * 100
            "taux_retard_pct": round((retards_parking / nb_total) * 100, 1),
            # (a) Estimation du temps perdu cumulé par tous les camions (b) Formule: depassement_moyen * total_cycles
            "temps_perdu_total_min": round(dep_parking * nb_total, 0),
            "causes": causes_par_poste.get("parking", [])
        },
        {
            "key": "bascule_tare",
            "etape": "Étape ③ (1er passage)",
            "nom": "Agence Logistique (Tare)",
            "action": "Pesage à vide du camion",
            # (a) Temps moyen réel de pesée à vide (b) Formule: sum(duree_bascule_tare) / nb_cycles
            "temps_moyen": avg_b_tare,
            # (a) Seuil maximal toléré configuré (b) Formule: settings.seuil_bascule_max
            "seuil_max": settings.seuil_bascule_max,
            # (a) Minutes excédentaires moyennes à la pesée tare (b) Formule: max(0, temps_moyen - seuil_max)
            "depassement": round(dep_b_tare, 1),
            # (a) Pourcentage de camions ayant dépassé le seuil en bascule tare (b) Formule: (nb_camions_retard_tare / total_cycles) * 100
            "taux_retard_pct": round((retards_b_tare / nb_total) * 100, 1),
            # (a) Temps perdu total cumulé à la pesée tare (b) Formule: depassement_moyen * total_cycles
            "temps_perdu_total_min": round(dep_b_tare * nb_total, 0),
            "causes": causes_par_poste.get("bascule", [])
        },
        {
            "key": "ensachage",
            "etape": "Étape ④",
            "nom": "Expéditions / Ensachage",
            "action": "Chargement des sacs de ciment",
            # (a) Temps moyen réel de chargement sous ensacheuse (b) Formule: sum(duree_ensachage) / nb_cycles
            "temps_moyen": avg_ensachage,
            # (a) Seuil maximal toléré configuré (b) Formule: settings.seuil_ensachage_max
            "seuil_max": settings.seuil_ensachage_max,
            # (a) Minutes excédentaires moyennes au chargement (b) Formule: max(0, temps_moyen - seuil_max)
            "depassement": round(dep_ensachage, 1),
            # (a) Pourcentage de camions ayant dépassé le seuil à l'ensachage (b) Formule: (nb_camions_retard_ensachage / total_cycles) * 100
            "taux_retard_pct": round((retards_ensachage / nb_total) * 100, 1),
            # (a) Temps perdu total cumulé à l'ensachage (b) Formule: depassement_moyen * total_cycles
            "temps_perdu_total_min": round(dep_ensachage * nb_total, 0),
            "causes": causes_par_poste.get("ensachage", [])
        },
        {
            "key": "bascule_brut",
            "etape": "Étape ③↩ (2ème passage)",
            "nom": "Agence Logistique (Brut)",
            "action": "Pesage camion plein & contrôle final",
            # (a) Temps moyen réel de pesée retour camion chargé (b) Formule: sum(duree_bascule_brut) / nb_cycles
            "temps_moyen": avg_b_brut,
            # (a) Seuil maximal toléré configuré (b) Formule: settings.seuil_bascule_max
            "seuil_max": settings.seuil_bascule_max,
            # (a) Minutes excédentaires moyennes à la pesée brut (b) Formule: max(0, temps_moyen - seuil_max)
            "depassement": round(dep_b_brut, 1),
            # (a) Pourcentage de camions ayant dépassé le seuil en bascule brut (b) Formule: (nb_camions_retard_brut / total_cycles) * 100
            "taux_retard_pct": round((retards_b_brut / nb_total) * 100, 1),
            # (a) Temps perdu total cumulé à la pesée brut (b) Formule: depassement_moyen * total_cycles
            "temps_perdu_total_min": round(dep_b_brut * nb_total, 0),
            "causes": [c for c in causes_par_poste.get("bascule", []) if "brut" in c["cause"].lower() or "bon" in c["cause"].lower()]
        }
    ]

    # Zone la plus pénalisante
    zone_bloquante = max(zones, key=lambda z: z["depassement"])

    return {
        "zones": zones,

        # (a) Nombre total de cycles de camions examinés (b) Formule: len(cycles_termines_30j)
        "nb_cycles_analyses": len(cycles),

        # (a) Zone avec le plus fort dépassement en minutes (b) Formule: max(zones, key=depassement)["nom"]
        "zone_la_plus_bloquante": zone_bloquante["nom"],

        # (a) Total des heures perdues excédentaires sur le site (b) Formule: sum(temps_perdu_total_min) / 60
        "total_temps_perdu_heures": round(sum(z["temps_perdu_total_min"] for z in zones) / 60, 1)
    }


@router.get("/rapport")
def get_rapport(
    periode: str = Query("aujourd_hui", enum=["aujourd_hui", "semaine", "mois"]),
    db: Session = Depends(get_db)
):
    """
    Rapport statistique complet pour la page Statistiques.
    Accepte : aujourd_hui | semaine | mois
    """
    now = datetime.utcnow()

    if periode == "aujourd_hui":
        date_debut = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_debut_prev = date_debut - timedelta(days=1)
        date_fin_prev = now - timedelta(days=1)
        periode_label = "Aujourd'hui"
    elif periode == "semaine":
        date_debut = now - timedelta(days=7)
        date_debut_prev = date_debut - timedelta(days=7)
        date_fin_prev = date_debut
        periode_label = "7 derniers jours"
    else:
        date_debut = now - timedelta(days=30)
        date_debut_prev = date_debut - timedelta(days=30)
        date_fin_prev = date_debut
        periode_label = "30 derniers jours"

    date_fin = now

    # ── Cycles période actuelle ───────────────────────────────────────────
    cycles_all = db.query(Cycle).filter(Cycle.entree_porte >= date_debut).all()
    # Pour les KPI de durées moyennes, on exclut les cycles anomalie (inférés, auto-fermés, FSM invalides)
    # afin d'éviter que des durées artificielles de 1 min ne contamine les statistiques usine.
    cycles_termines = [c for c in cycles_all if c.status == TruckStatus.TERMINE and not c.est_anomalie]
    cycles_en_cours = [c for c in cycles_all if c.status == TruckStatus.EN_COURS]
    cycles_anomalie = [c for c in cycles_all if c.est_anomalie]

    # ── Cycles période précédente (pour comparaison de tendance) ──────────
    cycles_prev_termines = db.query(Cycle).filter(
        Cycle.status == TruckStatus.TERMINE,
        Cycle.entree_porte >= date_debut_prev,
        Cycle.entree_porte < date_fin_prev
    ).all()

    nb_total = len(cycles_all)
    nb_termines = len(cycles_termines)
    nb_anomalie = len(cycles_anomalie)

    # (a) Taux de cycles ayant rencontré au moins une anomalie (b) Formule: (nb_anomalies / nb_total_cycles) * 100
    taux_anomalie = round((nb_anomalie / nb_total * 100), 1) if nb_total > 0 else 0.0

    # ── Temps de cycle (avec Percentiles P25/P75 au lieu du Min/Max) ───────
    def safe_avg(lst):
        vals = [v for v in lst if v and v > 0]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    def safe_median(lst):
        vals = [v for v in lst if v and v > 0]
        return round(statistics.median(vals), 1) if vals else 0.0

    def safe_quantile(lst, q):
        vals = sorted([v for v in lst if v and v > 0])
        if not vals:
            return 0.0
        if len(vals) == 1:
            return round(vals[0], 1)
        idx = (len(vals) - 1) * q
        floor_idx = int(idx)
        ceil_idx = floor_idx + 1 if floor_idx + 1 < len(vals) else floor_idx
        res = vals[floor_idx] + (vals[ceil_idx] - vals[floor_idx]) * (idx - floor_idx)
        return round(res, 1)

    durees_total = [c.duree_total for c in cycles_termines if c.duree_total and c.duree_total > 0]
    durees_total_prev = [c.duree_total for c in cycles_prev_termines if c.duree_total and c.duree_total > 0]

    # (a) Temps moyen de séjour usine sur la période actuelle (b) Formule: sum(duree_total) / nb_termines
    temps_moyen = safe_avg(durees_total)

    # (a) Temps moyen sur la période précédente équivalente (b) Formule: sum(duree_total_prev) / nb_prev_termines
    temps_moyen_prev = safe_avg(durees_total_prev)

    # (a) Variation en % par rapport à la période précédente (b) Formule: ((temps_actuel - temps_prev) / temps_prev) * 100
    variation_pct = 0.0
    if temps_moyen_prev > 0:
        variation_pct = round(((temps_moyen - temps_moyen_prev) / temps_moyen_prev) * 100, 1)

    tendance = "stable"
    if variation_pct > 2.0:
        tendance = "hausse"
    elif variation_pct < -2.0:
        tendance = "baisse"

    # (a) Médiane (50% des camions passent sous ce temps) (b) Formule: median(duree_total)
    temps_median = safe_median(durees_total)

    # (a) Premier quartile P25 (25% des camions les plus rapides) (b) Formule: quantile(duree_total, 0.25)
    temps_p25 = safe_quantile(durees_total, 0.25)

    # (a) Troisième quartile P75 (75% des camions, limite des 25% les plus lents) (b) Formule: quantile(duree_total, 0.75)
    temps_p75 = safe_quantile(durees_total, 0.75)

    # ── Liste brute des camions actuellement bloqués ────────────────────────
    camions_bloques_actuellement = []
    for c in cycles_en_cours:
        last_event = db.query(Event).filter(
            Event.truck_id == c.truck_id,
            Event.horodatage >= c.entree_porte
        ).order_by(Event.horodatage.desc()).first()

        poste_actuel = last_event.poste.value if last_event and hasattr(last_event.poste, "value") else (last_event.poste if last_event else "porte_usine")
        dernier_passage = last_event.horodatage if last_event else c.entree_porte
        if dernier_passage and dernier_passage.tzinfo is not None:
            dernier_passage = dernier_passage.replace(tzinfo=None)

        minutes_attente = round((now - dernier_passage).total_seconds() / 60, 1) if dernier_passage else 0.0

        # Seuil par poste pour considérer le camion comme "bloqué" / "en retard"
        seuil_poste_map = {
            "parking": settings.seuil_attente_parking_max,
            "bascule": settings.seuil_bascule_max,
            "ensachage": settings.seuil_ensachage_max,
            "porte_usine": settings.seuil_cycle_total_max,
        }
        seuil_tolere = seuil_poste_map.get(poste_actuel.lower(), 30)

        # Un camion est considéré BLOQUÉ s'il a dépassé le seuil autorisé au poste actuel
        if minutes_attente >= seuil_tolere:
            camions_bloques_actuellement.append({
                "truck_id": c.truck_id,
                "immatriculation": c.truck.immatriculation if c.truck else "Inconnu",
                "poste_actuel": poste_actuel,
                "minutes_attente_poste": minutes_attente,
                "entree_porte": c.entree_porte.isoformat() if c.entree_porte else None,
            })

    # Tri par temps d'attente au poste le plus élevé d'abord
    camions_bloques_actuellement.sort(key=lambda x: x["minutes_attente_poste"], reverse=True)

    # ── Durées par zone ───────────────────────────────────────────────────
    seuils = {
        "parking": settings.seuil_attente_parking_max,
        "bascule_tare": settings.seuil_bascule_max,
        "ensachage": settings.seuil_ensachage_max,
        "bascule_brut": settings.seuil_bascule_max,
    }
    zone_labels = {
        "parking": "Parking",
        "bascule_tare": "Bascule Tare",
        "ensachage": "Ensachage",
        "bascule_brut": "Bascule Brut",
    }
    zone_getters = {
        "parking": lambda c: c.duree_parking,
        "bascule_tare": lambda c: c.duree_bascule_tare,
        "ensachage": lambda c: c.duree_ensachage,
        "bascule_brut": lambda c: c.duree_bascule_brut,
    }

    durees_par_zone = []
    for key, label in zone_labels.items():
        vals = [zone_getters[key](c) for c in cycles_termines]
        moy = safe_avg(vals)
        seuil = seuils[key]
        dep = len([v for v in vals if v and v > seuil])
        durees_par_zone.append({
            "zone": label,
            "key": key,
            "moyenne": moy,
            "seuil": seuil,
            "depassements": dep
        })

    # ── Analyse statistique détaillée des causes de retard ────────────────
    # Récupérer le total des minutes de retard pour le calcul des parts en %
    total_minutes_retard_global = db.query(func.sum(Event.minutes_retard))\
        .filter(Event.horodatage >= date_debut, Event.delay_cause_id != None).scalar() or 1

    events_retard = db.query(
        Event.poste,
        DelayCause.nom,
        func.count(Event.id).label("count"),
        func.sum(Event.minutes_retard).label("total_minutes"),
        DelayCause.id.label("cause_id")
    ).join(DelayCause, Event.delay_cause_id == DelayCause.id).filter(
        Event.horodatage >= date_debut,
        Event.delay_cause_id != None
    ).group_by(Event.poste, DelayCause.nom, DelayCause.id).all()

    causes_detaillees = []
    for poste, cause_nom, count, total_mins, cause_id in events_retard:
        mins = int(total_mins or 0)
        pct_du_retard = round((mins / total_minutes_retard_global) * 100, 1)

        # Répartition de cette cause par transporteur
        transporteurs_impactes = db.query(Transporteur.nom, func.count(Event.id).label("cnt"))\
            .join(Truck, Truck.transporteur_id == Transporteur.id)\
            .join(Event, Event.truck_id == Truck.id)\
            .filter(Event.delay_cause_id == cause_id, Event.horodatage >= date_debut)\
            .group_by(Transporteur.nom).all()

        repartition_trans = [
            {"transporteur": t_nom, "occurrences": t_count}
            for t_nom, t_count in transporteurs_impactes
        ]

        causes_detaillees.append({
            "cause": cause_nom,
            "occurrences": count,
            "total_minutes": mins,
            "poste": poste.value if hasattr(poste, "value") else str(poste),
            "pct_du_retard": pct_du_retard,
            "repartition_transporteurs": sorted(repartition_trans, key=lambda x: x["occurrences"], reverse=True)
        })
    causes_detaillees = sorted(causes_detaillees, key=lambda x: x["total_minutes"], reverse=True)

    # ── Répartition des sources ───────────────────────────────────────────
    events_all = db.query(Event).filter(Event.horodatage >= date_debut).all()
    repartition_source = {"camera": 0, "agent_mobile": 0, "hybrid": 0, "simulation": 0}
    for ev in events_all:
        src = (ev.source or "camera").lower()
        if src in repartition_source:
            repartition_source[src] += 1
        elif src == "simulation":
            repartition_source["simulation"] += 1
        else:
            repartition_source["camera"] += 1

    # ── Évolution temporelle ──────────────────────────────────────────────
    evolution = []
    if periode == "aujourd_hui":
        # Par heure 05h→23h
        for h in range(5, 24):
            heure_debut = date_debut.replace(hour=h, minute=0, second=0)
            heure_fin = heure_debut + timedelta(hours=1)
            count = len([c for c in cycles_all if c.entree_porte and
                         heure_debut <= c.entree_porte.replace(tzinfo=None) < heure_fin])
            evolution.append({"heure": f"{h:02d}:00", "nb_camions": count})

    elif periode == "semaine":
        # Par jour sur les 7 derniers jours
        jours_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        for i in range(6, -1, -1):
            jour = now - timedelta(days=i)
            jour_debut = jour.replace(hour=0, minute=0, second=0, microsecond=0)
            jour_fin = jour_debut + timedelta(days=1)
            count = len([c for c in cycles_all if c.entree_porte and
                         jour_debut <= c.entree_porte.replace(tzinfo=None) < jour_fin])
            label = f"{jours_fr[jour.weekday()]} {jour.day:02d}"
            evolution.append({"heure": label, "nb_camions": count})

    else:
        # Par semaine sur les 4 dernières semaines
        for i in range(3, -1, -1):
            sem_debut = now - timedelta(days=(i + 1) * 7)
            sem_fin = now - timedelta(days=i * 7)
            count = len([c for c in cycles_all if c.entree_porte and
                         sem_debut <= c.entree_porte.replace(tzinfo=None) < sem_fin])
            evolution.append({"heure": f"Sem {4 - i}", "nb_camions": count})

    # ── Répartition globale du temps de retard par poste ──────────────────
    retard_global_par_poste = {
        "Parking": int(sum([max(0.0, c.duree_parking - settings.seuil_attente_parking_max) for c in cycles_termines])),
        "Bascule Tare": int(sum([max(0.0, c.duree_bascule_tare - settings.seuil_bascule_max) for c in cycles_termines])),
        "Ensachage": int(sum([max(0.0, c.duree_ensachage - settings.seuil_ensachage_max) for c in cycles_termines])),
        "Bascule Brut": int(sum([max(0.0, c.duree_bascule_brut - settings.seuil_bascule_max) for c in cycles_termines])),
    }

    # ── Performance des transporteurs ─────────────────────────────────────
    transporteurs = db.query(Transporteur).filter(Transporteur.est_actif == True).all()
    perf_transporteurs = []
    for t in transporteurs:
        truck_ids = [tr.id for tr in t.trucks]
        if not truck_ids:
            continue
        cycles_t = [c for c in cycles_termines if c.truck_id in truck_ids]
        if not cycles_t:
            continue
        temps_moy_t = safe_avg([c.duree_total for c in cycles_t])
        nb_anomalies_t = len([c for c in cycles_t if c.est_anomalie])
        
        # Minutes cumulées perdues (dépassements de l'objectif de 120 minutes)
        retard_cumule_min = int(sum([max(0.0, c.duree_total - 120.0) for c in cycles_t if c.duree_total]))

        # Recherche de la cause de retard la plus fréquente pour ce transporteur
        events_t = db.query(DelayCause.nom, func.count(Event.id).label("cnt"))\
            .join(Event, Event.delay_cause_id == DelayCause.id)\
            .filter(Event.truck_id.in_(truck_ids), Event.horodatage >= date_debut)\
            .group_by(DelayCause.nom)\
            .order_by(func.count(Event.id).desc())\
            .first()
        cause_principale = events_t[0] if events_t else "Aucune déclarée"

        taux_retard = round((nb_anomalies_t / len(cycles_t) * 100), 1) if cycles_t else 0.0
        perf_transporteurs.append({
            "transporteur": t.nom,
            "nb_rotations": len(cycles_t),
            "temps_moyen_min": temps_moy_t,
            "taux_retard_pct": taux_retard,
            "retard_cumule_min": retard_cumule_min,
            "cause_principale": cause_principale
        })

    return {
        "periode": periode,
        "periode_label": periode_label,
        "date_debut": date_debut.isoformat(),
        "date_fin": date_fin.isoformat(),
        "nb_cycles_total": nb_total,
        "nb_cycles_termines": nb_termines,
        "nb_cycles_en_cours": len(cycles_en_cours),
        "nb_cycles_anomalie": nb_anomalie,
        # (a) Pourcentage de camions avec anomalie (b) Formule: (nb_anomalie / nb_cycles_total) * 100
        "taux_anomalie_pct": taux_anomalie,
        # (a) Temps moyen de séjour en usine (b) Formule: sum(durees) / nb_termines
        "temps_moyen_cycle_min": temps_moyen,
        # (a) Pourcentage de variation du temps moyen vs période précédente (b) Formule: ((moyen - moyen_prev) / moyen_prev) * 100
        "variation_pct": variation_pct,
        # (a) Tendance par rapport à la période précédente (b) Formule: "hausse" if var > 2 else "baisse" if var < -2 else "stable"
        "tendance": tendance,
        # (a) Temps médian de séjour en usine (50% des camions sous cette durée) (b) Formule: median(durees)
        "temps_median_cycle_min": temps_median,
        # (a) Premier quartile P25 (limite des 25% les plus rapides) (b) Formule: quantile(durees, 0.25)
        "temps_p25_cycle_min": temps_p25,
        # (a) Troisième quartile P75 (limite des 25% les plus lents) (b) Formule: quantile(durees, 0.75)
        "temps_p75_cycle_min": temps_p75,
        # (a) Liste brute triée des camions actuellement bloqués au poste avec durée (b) Formule: sort_desc(camions_en_cours, minutes_attente_poste)
        "camions_bloques_actuellement": camions_bloques_actuellement,
        "durees_par_zone": durees_par_zone,
        "top_causes_retard": causes_detaillees,
        "repartition_source": repartition_source,
        "evolution_journaliere": evolution,
        "performance_transporteurs": perf_transporteurs,
        "retard_global_par_poste": retard_global_par_poste,
    }

