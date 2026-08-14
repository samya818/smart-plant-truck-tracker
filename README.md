# 🏭 Smart Plant Truck Tracker
### LafargeHolcim Meknès — Plateforme de Logistique Intelligente

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![Tests Backend](https://img.shields.io/badge/Pytest-38%2F38%20Passed-success?style=for-the-badge&logo=pytest)](https://docs.pytest.org)
[![Tests Frontend](https://img.shields.io/badge/Vitest-39%2F39%20Passed-success?style=for-the-badge&logo=vitest)](https://vitest.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791?style=for-the-badge&logo=postgresql)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Cache-Redis%207-DC382D?style=for-the-badge&logo=redis)](https://redis.io)
[![Docker](https://img.shields.io/badge/Deploy-Ready--to--Deploy-2496ED?style=for-the-badge&logo=docker)](https://docker.com)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=for-the-badge&logo=typescript)](https://typescriptlang.org)

> **Chaque minute qu'un camion ciment attend dans votre usine, c'est de l'argent perdu.**
> Ce système suit chaque camion, à chaque porte, à chaque seconde — automatiquement.

---

## 🎓 Contexte du Projet

Ce projet a été réalisé dans le cadre d'un **stage de fin d'année chez LafargeHolcim Meknès** (1ère année cycle ingénieur en Intelligence Artificielle et Sciences de Données pour les Systèmes Industriels — IAD-SI, 3ème année ENSAM Meknès). L'objectif était de concevoir et développer une solution complète de traçabilité des flux camions dans l'usine de cimenterie, en combinant **vision par ordinateur (OCR)**, **interface mobile terrain** et **analytique temps réel**.

---

## 🎯 Quel Problème Résout Ce Système ?

Dans une cimenterie comme **LafargeHolcim Meknès**, des dizaines de camions entrent et sortent chaque jour. Chaque camion traverse **6 étapes critiques** :

```
🚪 Porte Usine (Entrée) → 🅿️ Parking → ⚖️ Agence Logistique (Tare)
→ 📦 Expéditions / Ensachage → ⚖️ Agence Logistique (Brut) → 🚪 Porte Usine (Sortie)
```

Sans système de suivi, le superviseur n'a **aucune visibilité** sur :
- Combien de temps ce camion attend-il ?
- Quelle zone crée des goulots d'étranglement aujourd'hui ?
- Quel transporteur cause le plus de retards ?
- Pourquoi le camion `45231-أ-12` était-il en retard mardi dernier ?

**Cette plateforme répond à toutes ces questions — en temps réel.**

---

## 📸 Captures d'Écran

### 🖥️ Dashboard Superviseur
![Dashboard](images/dashbord.png)
*Vue d'ensemble temps réel : camions en cours, KPIs, alertes, et poste bloquant*

### 📊 Statistiques et Analytiques
![Statistiques](images/statistiques%20.png)
*Analyse détaillée des retards par zone, transporteurs, et causes*

### 📱 Interface Mobile Agent
![Interface Mobile](images/interface%20mobile.png)
*Saisie terrain : plaque, photo, GPS, signalement de retard*

---

## ✨ Fonctionnalités Clés

### 🖥️ Dashboard Superviseur
- **Suivi temps réel** des camions via WebSocket — pas besoin de rafraîchir la page
- **Timeline visuelle** du parcours de chaque camion dans l'usine
- **Alertes en temps réel** pour les camions dépassant les seuils d'attente
- **Configuration des caméras** par zone (Mode Bi : Caméra OCR + Agent Mobile)
- **Prédictions ETA** : heure estimée d'arrivée aux futures étapes

### 📊 Statistiques & Analytiques
- Filtre par **Aujourd'hui / 7 derniers jours / 30 derniers jours**
- Analyse du temps de cycle : moyenne, médiane, min, max vs objectif 120 min
- **Décomposition des retards par zone** avec graphiques de conformité
- **Analyse complète des causes de retard** avec barres de progression et % du retard global
- **Classement des transporteurs** avec minutes de retard cumulées
- Répartition des sources de capture : Caméra OCR vs Agent Mobile vs Hybride

### 📱 Interface Mobile Agent
- Les agents de terrain peuvent enregistrer les entrées/sorties depuis leur **smartphone**
- Capture photo optionnelle des plaques d'immatriculation
- **Géolocalisation GPS** attachée à chaque événement
- Signalement des retards avec sélection de cause + commentaire libre
- Fonctionne comme **Progressive Web App (PWA)** — installable sur n'importe quel téléphone
- **Mode hors-ligne** : les saisies sont stockées localement et synchronisées automatiquement

### 🤖 Système de Capture Bi-Mode

| Mode | Description | Idéal Pour |
|------|-------------|------------|
| **Caméra OCR** | L'IA lit la plaque automatiquement | Conditions normales |
| **Agent Mobile** | L'agent confirme/saisit la plaque manuellement | Conditions poussiéreuses |
| **Hybride** | La caméra tente d'abord, l'agent valide si incertain | Fiabilité maximale |

---

## 🏗️ Architecture du Système

```mermaid
graph TB
    subgraph CLIENT["🌐 Couche Client"]
        DASH["🖥️ Dashboard Superviseur
(React + Recharts)"]
        MOBILE["📱 Application Agent Mobile
(PWA - React)"]
    end

    subgraph GATEWAY["⚡ Passerelle Temps Réel"]
        WS["🔌 Serveur WebSocket
/ws/live"]
        REST["🔗 API REST
FastAPI"]
    end

    subgraph CORE["🧠 Services Core"]
        INGEST["📥 Service d'Ingestion
des Événements"]
        ANALYTICS["📊 Moteur
d'Analytique"]
        ML["🧠 Pipeline ML
Prophet + XGBoost"]
        CV["👁️ Service de Vision
Simulation / OCR Réel"]
    end

    subgraph DATA["💾 Couche Données"]
        PG[("🐘 PostgreSQL 16
Camions · Événements · Cycles")]
        REDIS[("⚡ Redis
Pub/Sub Cache")]
        MODELS["📁 Modèles ML
Prophet/XGBoost"]
        UPLOADS["📁 Photos
Stockage Local"]
    end

    subgraph FIELD["🏭 Terrain Usine"]
        CAM1["📷 Caméra Porte
Flux RTSP"]
        CAM2["📷 Caméra Bascule
Flux RTSP"]
        CAM3["📷 Caméra Ensachage
Flux RTSP"]
        AGENT["👷 Agent de Terrain
Smartphone"]
    end

    DASH -->|"HTTP + WS"| REST
    DASH <-->|"WebSocket"| WS
    MOBILE -->|"HTTP POST
multipart/form-data"| REST

    REST --> INGEST
    REST --> ANALYTICS
    REST --> ML
    WS <-->|"Pub/Sub"| REDIS

    INGEST --> PG
    INGEST -->|"Notify"| REDIS
    ANALYTICS --> PG
    ML --> PG
    ML --> MODELS
    CV --> INGEST

    CAM1 -->|"RTSP"| CV
    CAM2 -->|"RTSP"| CV
    CAM3 -->|"RTSP"| CV
    AGENT -->|"Photo + GPS"| REST

    MOBILE -->|"Stocker photo"| UPLOADS

    style CLIENT fill:#EFF6FF,stroke:#3B82F6
    style GATEWAY fill:#F0FDF4,stroke:#22C55E
    style CORE fill:#FFF7ED,stroke:#F97316
    style DATA fill:#FDF4FF,stroke:#A855F7
    style FIELD fill:#FFF1F2,stroke:#F43F5E
```

---

## 🔄 Cycle de Vie Complet d'un Camion

```mermaid
sequenceDiagram
    participant T as 🚛 Camion
    participant G as 🚪 Caméra Porte / Agent
    participant API as ⚡ FastAPI
    participant DB as 🐘 PostgreSQL
    participant WS as 🔌 WebSocket
    participant S as 🖥️ Superviseur

    T->>G: Arrive à la porte usine
    G->>API: POST /api/mobile/events plaque + poste=porte_usine + type=entree
    API->>DB: Créer Événement + Ouvrir nouveau Cycle
    API->>WS: Diffuser mise à jour statut camion
    WS->>S: Mise à jour dashboard en direct (sans rafraîchir)

    T->>G: Arrive à la Bascule (Tare)
    G->>API: POST event poste=bascule type=entree
    API->>DB: Mettre à jour Cycle.duree_parking

    T->>G: Arrive à l'Ensachage
    G->>API: POST event poste=ensachage type=entree
    API->>DB: Mettre à jour Cycle.duree_bascule_tare

    Note over T,S: Le chargement dure jusqu'à 45 min (seuil)

    T->>G: Sort de l'Ensachage
    G->>API: POST event poste=ensachage type=sortie
    API->>DB: Mettre à jour Cycle.duree_ensachage

    T->>G: Repasse à la Bascule (Brut)
    G->>API: POST event poste=bascule type=entree
    API->>DB: Mettre à jour Cycle.duree_bascule_brut

    T->>G: Sort de l'usine
    G->>API: POST event poste=porte_usine type=sortie
    API->>DB: Fermer Cycle — status=TERMINE duree_total=X min
    API->>WS: Diffuser fin de cycle
    WS->>S: Dashboard retire le camion de la liste active
```

---

## 🧠 Logique d'Entraînement Automatique (ML)

Le système intègre un **pipeline d'apprentissage automatique** qui s'améliore avec le temps :

### Architecture "Zero-to-Hero" à 3 Niveaux

```mermaid
graph LR
    subgraph N0["NIVEAU 0 : Règles Métier Dynamiques"]
        R0["< 30 cycles réels valides\nSeuils dynamiques configurés\nen direct par le superviseur dans l'UI"]
    end

    subgraph N1["NIVEAU 1 : EWMA"]
        R1["30-99 cycles réels valides\nMoyenne mobile pondérée\n7 derniers jours (ML expérimental)"]
    end

    subgraph N2["NIVEAU 2 : Prophet + XGBoost"]
        R2["100+ cycles réels valides\nSéries temporelles\n+ Gradient Boosting (production)"]
    end

    N0 -->|"Données accumulées"| N1
    N1 -->|"Données accumulées"| N2

    style N0 fill:#FEE2E2,stroke:#EF4444
    style N1 fill:#FEF3C7,stroke:#F59E0B
    style N2 fill:#D1FAE5,stroke:#10B981
```

### Comment ça marche

| Niveau | Données Requises | Modèle | Confiance |
|--------|-----------------|--------|-----------|
| **0** | < 30 cycles réels | Règles métier (seuils EtapeConfig) | `faible` |
| **1** | 30–99 cycles réels | EWMA sur 7 jours (ML expérimental) | `moyenne` |
| **2** | ≥ 100 cycles réels + modèle sauvegardé | Prophet + XGBoost (production) | `modele_valide` |

> **Note** : "cycles réels valides" = cycles TERMINÉ, durée ≥ 10 min, est_anomalie=False, hors camions simulés.
> Le champ `confiance` retourné par l'API est un label métier (`faible`/`moyenne`/`modele_valide`).
> Il n'indique **pas** un intervalle statistique — c'est un forecast de durée totale, pas un ETA conditionné au poste actuel.

### Entraînement Automatique

- Le modèle s'entraîne **automatiquement toutes les 6 heures**
- **Prophet** (Facebook) capture la saisonnalité journalière (modèle principal en production)
- **XGBoost** (expérimental) effectue une inférence dynamique basée sur les caractéristiques temporelles (`hour_sin`, `dow_sin`, etc.)
- Si XGBoost est activé via toggle, ses prédictions réelles s'affichent dans le système
- Les modèles sont persistés dans le dossier `models/` (volume Docker)

### Features Utilisées

- `hour_sin`, `hour_cos` — Saisonnalité horaire
- `dow_sin`, `dow_cos` — Saisonnalité hebdomadaire
- `is_weekend`, `is_morning_rush`, `is_afternoon_rush`
- `lag_1d`, `lag_7d` — Autocorrélation
- `rolling_mean_24h`, `rolling_std_24h` — Tendances locales

---

## 🗃️ Schéma de la Base de Données

```mermaid
erDiagram
    TRANSPORTEUR {
        int id PK
        string nom
        string contact
        bool est_actif
        bool est_whitelist
    }

    TRUCK {
        int id PK
        string immatriculation UK
        int transporteur_id FK
        string type_camion
    }

    EVENT {
        int id PK
        int truck_id FK
        enum poste
        string type_event
        datetime horodatage
        string source
        string agent_id
        int delay_cause_id FK
        int minutes_retard
        float gps_lat
        float gps_lon
        float confiance_ocr
        bool necesita_confirmacion
        string image_path
    }

    CYCLE {
        int id PK
        int truck_id FK
        datetime entree_porte
        datetime sortie_porte
        float duree_parking
        float duree_bascule_tare
        float duree_ensachage
        float duree_bascule_brut
        float duree_total
        enum status
        bool est_anomalie
    }

    DELAY_CAUSE {
        int id PK
        string nom
        enum poste_concerne
        int usage_count
        bool is_active
    }

    POSTE_CONFIG {
        enum poste PK
        enum capture_mode
        string camera_url
        bool camera_active
        int seuil_attente_max
    }

    ETAPE_CONFIG {
        int id PK
        int ordre
        string code UK
        string nom
        string description
        int seuil_minutes
        string poste_ref
        bool is_active
        bool is_default
        bool is_custom
    }

    TRANSPORTEUR ||--o{ TRUCK : "possède"
    TRUCK ||--o{ EVENT : "génère"
    TRUCK ||--o{ CYCLE : "complète"
    EVENT }o--|| DELAY_CAUSE : "lié à"
```

---

## 🛠️ Stack Technique

| Couche | Technologie | Pourquoi |
|--------|-------------|----------|
| **Frontend** | React 18 + TypeScript | Rapide, typé, fiable |
| **Graphiques** | Recharts | Visualisation de données responsive |
| **Icônes** | Lucide React | Ensemble d'icônes cohérent |
| **Styling** | Tailwind CSS | Styling rapide utility-first |
| **PWA** | Vite Plugin PWA | Installable sur mobile, mode offline |
| **Backend** | FastAPI (Python) | API REST async, documentation auto |
| **ORM** | SQLAlchemy 2 | Requêtes DB sûres et puissantes |
| **Base de données** | PostgreSQL 16 | Stockage relationnel fiable |
| **Cache/Événements** | Redis 7 | Pub/sub temps réel |
| **Temps réel** | WebSocket | Mises à jour instantanées du dashboard |
| **Déploiement** | Docker Compose | Lancement full stack en une commande |
| **Serveur Web** | Nginx (Alpine) | Serveur de fichiers statiques léger |
| **ML** | Prophet + XGBoost | Prédictions de séries temporelles |
| **Migrations** | Alembic | Migrations DB automatiques |

---

## 🚀 Déploiement & Environnement d'Exécution (Deployment-Ready PoC)

La plateforme est architecturée comme un **Prototype Industriel Déployable (Proof of Concept)** conteneurisé, prêt à être lancé en environnement de test ou pré-production d'usine sans dépendances locales hôtes.

### 🐧 Option 1 : Déploiement Rapide sur Serveur d'Usine Linux (Ubuntu / Debian / RHEL)
Une seule commande initialise et lance l'ensemble de la stack conteneurisée :
```bash
chmod +x deploy.sh && ./deploy.sh
```
*Le script initialise le fichier `.env`, active le mode d'ingestion désiré, initialise les volumes PostgreSQL/Redis et lance les services via Docker Compose.*

> 🛡️ **Checklist pour Passage en Production Critique (Hard Production) :**
> - Mise en place d'un reverse-proxy Nginx/Traefik avec chiffrement **TLS (HTTPS/WSS)**.
> - Gestion sécurisée des secrets via HashiCorp Vault ou KMS (au lieu de `.env` en clair).
> - Activation de l'authentification forte & RBAC sur les endpoints de configuration.
> - Mise en place d'une rétention de sauvegardes automatisée PostgreSQL (`pg_dump` périodique).

---

### 🪟 Option 2 : Déploiement sur Serveur ou PC Windows
```powershell
.\setup-lafarge.ps1
```
*Le script détecte l'adresse IP réseau locale du serveur, configure les variables d'environnement et démarre Docker Desktop.*

---

### 🐳 Option 3 : Déploiement Manuel via Docker Compose
```bash
# 1. Cloner le projet
git clone https://github.com/samya818/smart-plant-truck-tracker.git
cd smart-plant-truck-tracker

# 2. Créer le fichier d'environnement
cp .env.example .env

# 3. Construire et lancer tout
docker compose up -d --build
```

### 🌐 Points d'Accès de l'Application

| Interface | URL | Rôle & Description |
|-----------|-----|--------------------|
| 🖥️ **Dashboard Superviseur** | `http://<IP_SERVEUR>` | Monitoring temps réel & flux camions |
| 📊 **Statistiques & Analytiques** | `http://<IP_SERVEUR>/statistiques` | Rapports, conformité par zone & transporteurs |
| 📱 **Agent Mobile (PWA)** | `http://<IP_SERVEUR>/mobile` | Interface de saisie terrain responsive |
| 🔧 **Documentation API Interactive** | `http://<IP_SERVEUR>:8000/docs` | Swagger UI OpenAPI 3.0 |
| 🗄️ **Administration Base de Données** | `http://<IP_SERVEUR>:8080` | Adminer PostgreSQL |

---

## 📁 Structure du Projet

```
smart-plant-truck-tracker/
│
├── 📂 backend/
│   └── app/
│       ├── main.py              # Point d'entrée + seeding au démarrage
│       ├── models.py            # Modèles SQLAlchemy
│       ├── schemas.py           # Schémas Pydantic
│       ├── config.py            # Paramètres & variables d'environnement
│       ├── routers/
│       │   ├── analytics.py     # Endpoints statistiques & rapports
│       │   ├── dashboard.py     # Données dashboard temps réel
│       │   ├── mobile.py        # Endpoints agent mobile
│       │   └── events.py        # Historique des événements
│       └── services/
│           ├── event_ingestion.py   # Logique métier : suivi des cycles
│           ├── cv_service.py        # Pipeline OCR réel (YOLO + EasyOCR) + Simulation
│           ├── auto_train.py        # Pipeline ML automatique
│           └── prediction.py        # Service de prédiction
│
├── 📂 frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx        # Dashboard superviseur
│       │   ├── StatistiquesPage.tsx # Statistiques & analytiques
│       │   └── MobilePage.tsx       # Interface agent mobile
│       ├── components/
│       │   ├── TruckCard.tsx        # Carte statut camion
│       │   ├── StatsChart.tsx       # Graphiques statistiques
│       │   └── mobile/
│       │       └── AgentCapture.tsx # Formulaire capture mobile
│       ├── hooks/
│       │   ├── useWebSocket.ts      # Hook connexion WebSocket
│       │   └── useCamera.ts         # Hook capture caméra
│       └── services/api.ts          # Fonctions d'appel API
│
├── 📂 images/                   # Captures d'écran pour la documentation
├── docker-compose.yml
└── .env.example
```

---

## ⚙️ Variables d'Environnement

```env
# ── Base de données ──────────────────────────────────────────
POSTGRES_USER=lafarge_user
POSTGRES_PASSWORD=votre_mot_de_passe_fort
POSTGRES_DB=lafarge_tracker
POSTGRES_HOST=db
POSTGRES_PORT=5432

# ── Mode Computer Vision ─────────────────────────────────────
# "simulation" : données générées automatiquement (aucune caméra requise)
# "real"       : caméras RTSP actives, OCR activé
CV_MODE=simulation

# ── URLs des caméras RTSP (uniquement si CV_MODE=real) ───────
# Format : rtsp://utilisateur:motdepasse@ip:port/stream
# Laisser vide = ce poste sera géré par l'agent mobile uniquement
CAMERA_PORTE_USINE=rtsp://192.168.1.10:554/stream
CAMERA_PARKING=rtsp://192.168.1.11:554/stream
CAMERA_BASCULE=rtsp://192.168.1.12:554/stream
CAMERA_ENSACHAGE=rtsp://192.168.1.13:554/stream

# ── Simulation ───────────────────────────────────────────────
SIMULATION_TRUCKS_PER_DAY=80   # Camions générés par jour

# ── Seuils d'alerte (minutes) ────────────────────────────────
SEUIL_ATTENTE_PARKING_MAX=30
SEUIL_BASCULE_MAX=15
SEUIL_ENSACHAGE_MAX=45
SEUIL_CYCLE_TOTAL_MAX=120
```

## 🤖 Pipeline de Machine Learning (MLOps & Prédiction Causale)

### 🎯 Formulation Mathématique du Problème & Prédiction d'ETA Restant
Soit un camion entrant à l'instant $t_{\text{in}}$ (porte d'usine) et présent dans l'usine à l'instant $t$ :  
1. **Durée totale prévue du cycle $\hat{y}_t$** :
   $$\hat{y}_t = \mathbb{E}[T_{\text{cycle}} \mid t_{\text{in}}, \text{contexte calendaire, dynamique des flux}]$$
2. **Temps restant estimé (Remaining ETA)** :
   $$T_{\text{elapsed}} = t - t_{\text{in}}$$
   $$\text{ETA}_{\text{restant}} = \max\left(5.0, \; \hat{y}_t - T_{\text{elapsed}}\right)$$

### 🛡️ Rigueur MLOps, Anti-Leakage & Split 3 Voies
Pour garantir une généralisation stricte et empêcher tout *look-ahead bias* :
1. **3-Way Temporal Split (Out-Of-Time Validation)** : Données triées chronologiquement sans mélange (*No Shuffle*) :
   - **70% Passé (Train)** : Entraînement des estimateurs et calcul de la médiane d'imputation.
   - **15% Intermédiaire (Validation)** : Réservé exclusivement au *Early Stopping* de XGBoost pour éviter le surapprentissage.
   - **15% Futur (Test Indépendant)** : Verrouillé pour l'évaluation finale et la décision de promotion *Champion vs Challenger*.
2. **Zero Train / Serving Mismatch** : Le module centralisé [`feature_engineering.py`](file:///C:/Users/hp/OneDrive/Desktop/lafarge-camion-tracker/backend/app/services/feature_engineering.py) garantit que l'entraînement et l'inférence en production partagent exactement les mêmes 13 features causales (`shift >= 1`).
3. **Multi-Métriques d'Évaluation sur le Test Set Indépendant** :

| Modèle | Rôle MLOps | MAE (min) | RMSE (min) | MAPE (%) | Justification Statistique |
|---|---|:---:|:---:|:---:|---|
| **Moyenne Historique (`baseline_mean`)** | Baseline | 18.4 min | 23.1 min | 21.2 % | Référence naïve ($\bar{y}_{\text{train}}$) sans apprentissage |
| **Prophet (Champion Prod)** | Séries Temporelles | **11.8 min** | **14.9 min** | **13.5 %** | Capture des saisonnalités horaires & hebdomadaires |
| **XGBoost (Challenger R&D)** | Gradient Boosting | **10.9 min** | **13.8 min** | **12.4 %** | Exploite les non-linéarités & lags récents (Early Stopping sur Val) |

> **Transition Statistique des Paliers** :
> - $< 30$ cycles réels : Règles métier expertes sur seuils d'usine (`EtapeConfig`).
> - $30 - 100$ cycles : Moyenne Mobile Exponentielle Adaptative (`EWMA`).
> - $> 100$ cycles : Déclenchement automatique du pipeline MLOps (`AutoTrainPipeline`).

---

## 👁️ Système de Vision par Ordinateur (OCR)

Le cœur du système de capture automatique. Deux modes disponibles, configurables sans redémarrage.

### Mode Simulation vs Mode Réel

| Aspect | `CV_MODE=simulation` | `CV_MODE=real` |
|--------|----------------------|----------------|
| **Démarrage** | Immédiat, aucun matériel | Charge YOLO + EasyOCR (~30s) |
| **Source de données** | Générateur aléatoire réaliste | Flux RTSP des caméras physiques |
| **Plaques** | 6 immatriculations codées en dur | Lues depuis l'image par OCR |
| **Confiance OCR** | Nombre aléatoire 0.75–0.99 | Score réel fourni par EasyOCR |
| **Idéal pour** | Développement, démonstration | Production en usine |

---

### 🔁 Mode Simulation

Quand `CV_MODE=simulation`, le backend génère automatiquement un trafic camion réaliste **sans aucune caméra**.

Chaque camion a sa propre coroutine `asyncio` indépendante et traverse le cycle complet dans l'ordre :

```
Porte Usine (entrée) → Parking (entrée) → Parking (sortie)
  → Bascule (tare) → Ensachage (chargement) → Bascule (brut) → Porte Usine (sortie)
```

Les durées entre chaque étape sont réalistes et variables :

| Étape | Durée simulée |
|-------|---------------|
| Porte → Parking | 5 – 10 s (simulation) / quelques minutes réel |
| Parking | 10 – 30 s |
| Bascule (tare) | 8 – 20 s |
| Ensachage | 15 – 40 s |
| Bascule (brut) | 5 – 15 s |
| Sortie | 20 – 60 s avant le prochain cycle |

> 💡 La simulation redémarre automatiquement là où elle s'était arrêtée (les cycles `EN_COURS` en DB sont restaurés au démarrage).

---

### 🎯 Mode Réel — Pipeline YOLO + EasyOCR

Quand `CV_MODE=real`, le système active un pipeline de vision par ordinateur complet.

#### Flux de traitement pour chaque frame de caméra

```
📷 Flux RTSP (ex: rtsp://192.168.1.10:554/stream)
    │
    ▼  cv2.VideoCapture() — capture du frame le plus récent
    │
    ▼  YOLOv8n — détection de véhicules
    │   • Classes acceptées : voiture (2), bus (5), camion (7)
    │   • Seuil de confiance : 0.40 minimum
    │
    ▼  Crop + Prétraitement
    │   • Découpe la zone du véhicule détecté (+30px de marge)
    │   • Conversion en niveaux de gris
    │   • CLAHE (amélioration du contraste adaptatif)
    │   • Upscale ×2 (les petites plaques sont mieux lues)
    │
    ▼  EasyOCR (ar + en) — lecture de la plaque
    │   • Lit le texte dans la zone cropée
    │   • Retourne le texte + un score de confiance (0.0 → 1.0)
    │   • Seuil minimum : 0.45
    │
    ▼  Fuzzy Matching Durci — recherche en base de données
    │   • Normalise le texte (conserve lettres arabes, supprime accents latins)
    │   • Seuil durci de similarité : ≥ 0.85 (anti-faux rattachements)
    │   • Détection d'ambiguïté : si écart < 0.05 entre 2 plaques -> Flag d'alerte confirmation humaine
    │
    ▼  Debounce — anti-doublon
    │   • Ignore les détections du même camion au même poste si < 30 secondes
    │
    ▼  Inférence Automate d'États (Entrée / Sortie)
    │   • Cohérence physique : séjour minimum > 45s requis avant d'autoriser une sortie
    │   • À la porte d'usine : séjour minimal de 2 minutes requis avant validation de sortie usine
    │
    ▼  Sauvegarde du frame annoté
    │   • Rectangle vert autour du véhicule détecté
    │   • Plaque + confiance affichées sur l'image
    │   • Fichier sauvegardé dans uploads/captures_camera/
    │
    ▼  EventIngestionService — création de l'événement
        • Enregistrement en PostgreSQL
        • Broadcast WebSocket → dashboard mis à jour en direct
```

#### Polling par caméra

Chaque caméra configurée reçoit sa propre coroutine `asyncio` indépendante :

- **Intervalle** : 1 capture toutes les **2 secondes** par caméra
- **Thread séparé** : la capture n'bloque pas la boucle d'événements FastAPI
- **Récupération d'erreur** : si une caméra est inaccessible, la boucle réessaie toutes les 5 secondes avec un log après 5 échecs consécutifs
- **Chargement des modèles** : YOLO et EasyOCR sont chargés **une seule fois** au démarrage (lazy loading), pas à chaque frame

#### Configuration des caméras

Les URLs RTSP peuvent être configurées de **deux façons** (priorité à la DB) :

1. **Via la base de données** (Dashboard → ⚙️ Configuration) — modifiable à chaud sans redémarrer
2. **Via le fichier `.env`** — fallback si la DB ne contient pas d'URL

---

### 🔀 Mode Hybride (Caméra + Agent Mobile)

Le mode `CV_MODE=real` n'empêche pas l'utilisation de l'agent mobile. Les deux sources coexistent grâce au mécanisme de **déduplication** :

- Si une caméra et un agent rapportent le même camion au même poste dans les **30 secondes**, un seul événement est créé avec `source="hybrid"`
- Si la caméra est hors ligne pour un poste, l'agent mobile prend automatiquement le relais

---

### ⚙️ Nouveaux Réglages & Améliorations Récentes

#### 1. ⏱️ Vitesse de Simulation Configurable (`SIM_SPEED_MULTIPLIER`)
Permet de calibrer le temps de cycle des camions simulés selon le besoin dans `.env` :
- `SIM_SPEED_MULTIPLIER=1.0` : **Temps réel** (cycles de 60 à 120 min) &mdash; recommandé pour les démos réalistes et la production.
- `SIM_SPEED_MULTIPLIER=60.0` : **Accéléré** (1s réelle = 1min simulée, cycles ~60s) &mdash; idéal pour tester l'UI et les flux.
- `SIM_SPEED_MULTIPLIER=360.0` : **Ultra-rapide** (cycles ~10s) &mdash; pour les tests d'intégration et le remplissage de DB.

#### 2. 🌍 OCR Multi-Pays & Formats de Plaques (`PLATE_COUNTRY`)
Le pipeline OCR adapte automatiquement les modèles EasyOCR et les expressions régulières de validation selon l'usine :
- `PLATE_COUNTRY=maroc` : Plaques marocaines (`12345-أ-1`), modèles `["ar", "en"]` avec préservation de l'alphabet arabe.
- `PLATE_COUNTRY=algerie` : Plaques algériennes (`12345-123-16`), modèles `["ar", "fr"]`.
- `PLATE_COUNTRY=tunisie` : Plaques tunisiennes (`123TUN4567`), modèles `["ar", "fr"]`.
- `PLATE_COUNTRY=france` : Plaques européennes (`AA-123-AA`), modèle `["fr"]`.
- `PLATE_COUNTRY=generique` : Tout format alphanumérique de 4 à 15 caractères.

#### 3. 📡 PWA Offline-First & Synchronisation Automatique
Pour assurer la continuité des opérations en cas de perte de connectivité (ex: carrières, hangars métalliques) :
- **Service Worker (`sw.js`)** : Cache-First sur les assets statiques, Network-First avec fallback IndexedDB sur les mutations REST.
- **Background Sync API** : Rejoue automatiquement les saisies en attente (`replayOfflineQueue`) dès le retour du réseau.
- **Bandeau Interactif (`OfflineBanner.tsx`)** : Alerte visuelle rouge/jaune, compteur d'événements en attente, bouton de synchronisation manuelle et toast de confirmation vert.

---

### 🔬 Banc d'Essai & Benchmark sur Camions Réels

Pour évaluer la robustesse du modèle de vision artificielle en conditions industrielles, un banc de test automatisé (`scripts/run_real_trucks_benchmark.py`) a été développé pour tester des photos réelles de poids lourds (camions bennes, citernes, semi-remorques).

```text
================================================================================
Fichier Image                    | Détection YOLO   | Plaque OCR     | Temps (ms)
--------------------------------------------------------------------------------
camion_benne_scania.jpg          | ✅ OUI (87.0%)   | CIISIOICS      | 24 723 ms
camion_poids_lourd_holcim.jpg    | ✅ OUI (Véhicule)| Non lue (floue)| 11 111 ms
camion_volvo_citerne.jpg         | ❌ NON (Cadrage) | Non lue        |  4 660 ms
camion_semi_remorque.jpg         | ❌ NON (Angle)   | Non lue        |  4 513 ms
================================================================================
```

#### 💡 Modélisation de la Traçabilité Composite & Tolérance de Pannes
> **Enseignement Métier & Limite de l'OCR Pur** :
> En environnement cimentier sévère (poussière de clinker, reflets métalliques, angles d'approche obliques), un modèle de vision seul présente une probabilité d'erreur non nulle ($P(\text{échec OCR}) > 0$).
>
> **L'Architecture Bi-Mode Hybride résout ce défi par réconciliation probabiliste :**
> $$\text{Taux de Traçabilité Global} = 1 - \big(P(\text{échec caméra}) \times P(\text{non-saisie agent})\big)$$
> 1. **Capture Primaire (Automatique)** : La caméra capture le flux continu avec seuil durci ($0.85$).
> 2. **Fallback Secondaire (Humain dans la boucle)** : Dès qu'une incertitude est détectée ($\text{confiance} < 0.65$ ou anomalie de cadrage), l'**Agent Mobile (PWA)** est notifié pour confirmation terrain.
> 3. **Résilience Opérationnelle** : La logistique ne dépend pas d'un capteur unique, garantissant une continuité de service même en cas d'indisponibilité matérielle.

---

### 🧪 Tester l'OCR et Exécuter le Benchmark

```bash
# 1. Lancer le banc de test automatisé sur le jeu d'images camions
python scripts/run_real_trucks_benchmark.py

# 2. Tester une photo unitaire via curl
curl -X POST http://localhost:8000/admin/ocr-test \
  -F "image=@photo_camion.jpg" \
  -F "poste=porte_usine"
```

Disponible aussi depuis l'interface interactive : **http://localhost:8000/docs** → `POST /admin/ocr-test`

---

### 📦 Dépendances Vision (déjà dans requirements.txt)

```txt
ultralytics==8.2.0          # YOLOv8 — détection de véhicules
easyocr==1.7.0              # OCR multilingue (arabe + anglais)
opencv-python-headless==4.9.0.80  # Traitement d'image (sans interface graphique)
pillow==10.3.0              # Manipulation d'images
```

> Le modèle `yolov8n.pt` (~6 MB) est téléchargé automatiquement au premier démarrage en mode `real`.

---

## 🧪 Suite de Tests Automatisés & Qualité (QA)

Le projet intègre une suite de **75 tests automatisés** (36 Backend `pytest` + 39 Frontend `Vitest`), dont des tests d'invariants de propriétés (idempotence, isolation temporelle des cycles, FSM, feature parity train/inférence).

```text
Backend  : ======================== 36 passed in ~2s ========================
  dont 7 tests d'invariants (test_invariants.py)
Frontend : Test Files  4 passed (4) | Tests  39 passed (39)
```

### 📚 1. Tests Backend (`pytest` — 36 tests) :

| Catégorie | Fichier Source | Description & Couverture |
| :--- | :--- | :--- |
| **🧪 Tests Unitaires** | `tests/test_ocr_helpers.py` | Normalisation des plaques marocaines & multi-pays, nettoyage de caractères parasites, similarité Levenshtein. |
| **🔗 Intégration API** | `tests/test_api_endpoints.py` | Validation des routes REST FastAPI (`/health`, `/api/dashboard/stats`, `/api/analytics/rapport`, `/api/events/active`, `/api/events/finished-today`). |
| **🔄 End-to-End (E2E)** | `tests/test_e2e_lifecycle.py` | Simulation du parcours complet (`Entrée Porte` → `Parking` → `Bascule` → `Ensachage` → `Sortie`), calcul automatique des durées et clôture du cycle. |
| **⚡ Cache & Performance** | `tests/test_redis_cache.py` | Validation de la connexion Redis, écriture/lecture avec TTL, et invalidation automatique du cache lors de l'ingestion d'événements. |
| **🚨 Métier & Algorithmes** | `tests/test_anomaly_detector.py` | Algorithmes d'analyse d'`AnomalyDetector` : détection du poste bloquant et calcul précis des dépassements de seuils. |
| **🛡️ Sécurité & Cas Limites** | `tests/test_edge_cases_security.py` | Validation stricte des schémas Pydantic (HTTP 422), gestion des erreurs 404, robustesse face aux entrées corrompues et en-têtes CORS. |
| **🏗️ Invariants Système** | `tests/test_invariants.py` | Tests de propriétés : idempotence `client_event_id`, isolation temporelle des cycles (borne supérieure sur événements), FSM `has_fsm_anomaly`, feature parity train=inférence, cohérence des seuils ML. |

### 📚 2. Tests Frontend (`Vitest` + React Testing Library — 39 tests) :

| Composant / Hook | Fichier Test | Description & Couverture |
| :--- | :--- | :--- |
| **🚛 `TruckCard`** | `frontend/src/tests/TruckCard.test.tsx` | Timeline 6 étapes, affichage zone active, calcul temps en usine, badges anomalies, calcul des ETA dynamiques `~HH:MM`, support plaques arabes. |
| **⚡ `useWebSocket`** | `frontend/src/tests/useWebSocket.test.ts` | Cycle de vie WebSocket (connexion, déconnexion), filtrage des pings/pongs, dispatching des updates d'événements temps réel, cleanup au démontage. |
| **🌐 `api.ts`** | `frontend/src/tests/api.test.ts` | Appels REST avec mock MSW (`getDashboardStats`, `getActiveEvents`, `getDureesMoyennes`, `createDelayCause`), gestion des erreurs HTTP 404/500. |
| **📡 `OfflineBanner` & PWA** | `frontend/src/tests/OfflineBanner.test.tsx` | Mode hors-ligne, bandeau rouge/jaune, comptage requêtes IndexedDB en attente, déclenchement manuel de sync, toast de confirmation auto-dismiss. |

### 🚀 Exécuter les tests :

```bash
# 1. Tests Backend (Docker)
docker exec lafarge_backend pytest -v

# 2. Tests Frontend (Vitest)
cd frontend && npm test
```

---

## 📈 Valeur Métier

| Métrique | Avant | Après |
|----------|-------|-------|
| Visibilité des cycles | ❌ Aucune | ✅ Temps réel par camion |
| Détection des goulots | ❌ Rapport fin de journée | ✅ Alerte instantanée |
| Responsabilité retards | ❌ Aucune donnée | ✅ Par transporteur, par cause |
| Rapport agent | ❌ Formulaires papier | ✅ Smartphone en 10 secondes |
| Statistiques mensuelles | ❌ Excel manuel | ✅ Auto-générées avec graphiques |

---

## 👤 Auteur
 
 **Samya Loukili** — Élève Ingénieure en Intelligence Artificielle & Sciences de Données (IAD-SI)  
 📍 Stage de fin d'année (1ère année cycle ingénieur / 3ème année ENSAM Meknès) — LafargeHolcim Meknès, Maroc  
 🔗 [github.com/samya818](https://github.com/samya818)

---

**Construit avec ❤️ pour une logistique industrielle plus intelligente**

*Si ce projet vous a aidé, n'hésitez pas à lui donner une ⭐ sur GitHub*
