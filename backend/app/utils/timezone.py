"""
Utilitaire de gestion des fuseaux horaires et de la journée métier de l'usine.
Toutes les dates affichées ou filtrées doivent utiliser cette référence unique.
"""
from datetime import datetime, timedelta, timezone

# Fuseau horaire officiel de l'usine LafargeHolcim Meknès (Maroc UTC+1)
TZ_MAROC = timezone(timedelta(hours=1))


def get_business_now() -> datetime:
    """Retourne l'heure locale actuelle de l'usine (Maroc UTC+1)."""
    return datetime.now(tz=TZ_MAROC)


def get_start_of_business_day(reference_dt: datetime = None) -> datetime:
    """
    Retourne le début de la journée métier courante de l'usine (00:00:00 heure du Maroc),
    convertie en datetime UTC naïf compatible avec le stockage en base PostgreSQL/SQLite.
    
    Exemple : le 14 août à 00:30 (UTC+1) au Maroc, la journée a commencé à 00:00:00 (UTC+1),
    soit le 13 août à 23:00:00 UTC.
    """
    if reference_dt is None:
        now_plant = get_business_now()
    else:
        if reference_dt.tzinfo is None:
            now_plant = reference_dt.replace(tzinfo=timezone.utc).astimezone(TZ_MAROC)
        else:
            now_plant = reference_dt.astimezone(TZ_MAROC)

    start_plant = now_plant.replace(hour=0, minute=0, second=0, microsecond=0)
    # Convertir en UTC naïf pour les requêtes SQL
    return start_plant.astimezone(timezone.utc).replace(tzinfo=None)
