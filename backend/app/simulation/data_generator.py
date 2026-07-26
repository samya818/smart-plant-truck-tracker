"""
Générateur de données synthétiques crédibles avec logique de cycle respectée.
Simule le flux complet de camions sur plusieurs jours.
"""
import random
from datetime import datetime, timedelta
from faker import Faker
from typing import List, Dict

fake = Faker()

TEMPS_MOYENS = {
    "parking": (10, 25),
    "bascule_tare": (3, 8),
    "ensachage": (20, 40),
    "bascule_brut": (3, 8),
    "sortie": (2, 5)
}

TRANSPORTEURS = [
    "Trans Meknes", "Atlas Logistique", "Maroc Transport",
    "Sahara Camions", "Fes Cargo", "Rabat Transit"
]


def generate_moroccan_plate() -> str:
    """Génère une plaque marocaine réaliste."""
    nums = random.randint(10000, 99999)
    lettres = random.choice(["أ", "ب", "د", "و", "ط", "س", "ف", "ق", "ش", "م", "ن", "ل", "ه", "ي"])
    region = random.randint(1, 99)
    return f"{nums}-{lettres}-{region}"


def simuler_journee(date: datetime, nb_camions: int) -> List[Dict]:
    """Simule une journée complète à l'usine avec logique de cycle."""
    events = []

    for i in range(nb_camions):
        arrival_offset = random.randint(0, 12 * 60)
        current = date.replace(hour=6, minute=0) + timedelta(minutes=arrival_offset)

        plaque = generate_moroccan_plate()
        company = random.choice(TRANSPORTEURS)
        truck = {"immatriculation": plaque, "transporteur_nom": company}

        # 1. PORTE USINE — Entrée
        events.append({"truck": truck, "poste": "porte_usine", "type": "entree", "horodatage": current})

        # 2. PARKING (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "parking", "type": "entree", "horodatage": current})
        
        parking_duration = random.randint(*TEMPS_MOYENS["parking"])
        cause_parking = None
        if random.random() < 0.1:
            parking_duration += random.randint(15, 45)
            cause_parking = "Attente opérateur"
            
        current += timedelta(minutes=parking_duration)
        events.append({"truck": truck, "poste": "parking", "type": "sortie", "horodatage": current, "cause_retard": cause_parking})

        # 3. BASCULE — Tare (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "bascule", "type": "entree", "horodatage": current})
        current += timedelta(minutes=random.randint(*TEMPS_MOYENS["bascule_tare"]))
        events.append({"truck": truck, "poste": "bascule", "type": "sortie", "horodatage": current})

        # 4. ENSACHAGE (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "ensachage", "type": "entree", "horodatage": current})
        duree_ensachage = random.randint(*TEMPS_MOYENS["ensachage"])
        cause_ensachage = None
        if random.random() < 0.15:
            duree_ensachage += random.randint(20, 60)
            cause_ensachage = random.choice([
                "Panne ensacheuse", "Rupture sacs", "Attente qualité",
                "Changement produit", "Maintenance"
            ])
        current += timedelta(minutes=duree_ensachage)
        events.append({"truck": truck, "poste": "ensachage", "type": "sortie", "horodatage": current, "cause_retard": cause_ensachage})

        # 5. BASCULE — Brut (Entrée & Sortie)
        current += timedelta(minutes=random.randint(2, 5))
        events.append({"truck": truck, "poste": "bascule", "type": "entree", "horodatage": current})
        current += timedelta(minutes=random.randint(*TEMPS_MOYENS["bascule_brut"]))
        events.append({"truck": truck, "poste": "bascule", "type": "sortie", "horodatage": current})

        # 6. PORTE USINE — Sortie
        current += timedelta(minutes=random.randint(*TEMPS_MOYENS["sortie"]))
        events.append({"truck": truck, "poste": "porte_usine", "type": "sortie", "horodatage": current})

    return events


def run_full_simulation(days: int = 30, trucks_per_day: int = 80) -> List[Dict]:
    """Lance la simulation sur N jours."""
    all_events = []
    base_date = datetime.now() - timedelta(days=days)

    for day in range(days):
        date = base_date + timedelta(days=day)
        if date.weekday() >= 5:
            nb = int(trucks_per_day * 0.3)
        else:
            nb = int(trucks_per_day * random.uniform(0.8, 1.2))
        all_events.extend(simuler_journee(date, nb))

    return all_events
