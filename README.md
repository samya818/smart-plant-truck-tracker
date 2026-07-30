# 🏭 Smart Plant Truck Tracker
### LafargeHolcim Meknès — Plateforme de Logistique Intelligente

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791?style=for-the-badge&logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=for-the-badge&logo=docker)](https://docker.com)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=for-the-badge&logo=typescript)](https://typescriptlang.org)

> **Chaque minute qu'un camion ciment attend dans votre usine, c'est de l'argent perdu.**
> Ce système suit chaque camion, à chaque porte, à chaque seconde — automatiquement.

---

## 🎓 Contexte du Projet

Ce projet a été réalisé dans le cadre d'un **stage d'initiation chez LafargeHolcim Meknès**, leader mondial des matériaux de construction. L'objectif était de concevoir et développer une solution complète de traçabilité des flux camions dans l'usine de cimenterie, en combinant **vision par ordinateur (OCR)**, **interface mobile terrain** et **analytique temps réel**.

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
    subgraph N0["NIVEAU 0 : Règles Métier"]
        R0["< 50 événements
Seuils configurables
par le superviseur"]
    end

    subgraph N1["NIVEAU 1 : EWMA"]
        R1["50-499 événements
Moyenne mobile pondérée
7 derniers jours"]
    end

    subgraph N2["NIVEAU 2 : Prophet + XGBoost"]
        R2["500+ événements
Séries temporelles
+ Gradient Boosting"]
    end

    N0 -->|"Données accumulées"| N1
    N1 -->|"Données accumulées"| N2

    style N0 fill:#FEE2E2,stroke:#EF4444
    style N1 fill:#FEF3C7,stroke:#F59E0B
    style N2 fill:#D1FAE5,stroke:#10B981
```

### Comment ça marche

| Niveau | Données Requises | Modèle | Précision |
|--------|-----------------|--------|-----------|
| **0** | Aucune | Règles métier (seuils) | Basique |
| **1** | 50+ événements | EWMA (moyenne mobile) | Moyenne |
| **2** | 500+ événements | Prophet + XGBoost | Élevée |

### Entraînement Automatique

- Le modèle s'entraîne **automatiquement toutes les 6 heures**
- **Prophet** (Facebook) capture la saisonnalité journalière
- **XGBoost** (expérimental) teste si un modèle plus complexe améliore la précision
- Si XGBoost bat Prophet de plus de 5%, il devient le nouveau modèle
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

## 🚀 Démarrage Rapide — 3 Commandes

### Prérequis
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé
- [Git](https://git-scm.com/) installé

### Installation

```bash
# 1. Cloner le projet
git clone https://github.com/samya818/smart-plant-truck-tracker.git
cd smart-plant-truck-tracker

# 2. Créer le fichier d'environnement
cp .env.example .env

# 3. Construire et lancer tout
docker compose up -d --build
```

> ✅ C'est tout. Les 5 services démarrent automatiquement.

### Accéder à l'Application

| Interface | URL | Description |
|-----------|-----|-------------|
| 🖥️ **Dashboard Superviseur** | http://localhost | Écran principal de monitoring |
| 📊 **Statistiques** | http://localhost/statistiques | Analytiques et rapports |
| 📱 **Agent Mobile** | http://localhost/mobile | Interface terrain |
| 🔧 **Documentation API** | http://localhost:8000/docs | Explorateur API interactif |
| 🗄️ **Admin Base de Données** | http://localhost:8080 | Adminer (navigateur DB) |

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
│           ├── cv_service.py        # Simulation caméra / OCR réel
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
# Base de données
POSTGRES_USER=lafarge_user
POSTGRES_PASSWORD=votre_mot_de_passe_fort
POSTGRES_DB=lafarge_tracker

# Mode application
CV_MODE=simulation          # "simulation" ou "real"
SIMULATION_TRUCKS_PER_DAY=80

# Seuils (minutes)
SEUIL_ATTENTE_PARKING_MAX=30
SEUIL_BASCULE_MAX=15
SEUIL_ENSACHAGE_MAX=45
SEUIL_CYCLE_TOTAL_MAX=120
```

---

## 🎬 Comment Fonctionne la Simulation

Quand `CV_MODE=simulation`, le backend génère automatiquement un trafic camion réaliste :

- **80 camions/jour** par défaut (configurable)
- Les camions arrivent entre **06:00 et 18:00**
- Chaque camion traverse les 6 étapes avec des durées réalistes
- Des retards et anomalies aléatoires sont injectés (~15% des cycles)
- Le dashboard se met à jour en direct au fur et à mesure

> **Cela permet de tester le système complet sans aucune caméra physique.**

Pour utiliser de vraies caméras, mettez `CV_MODE=real` dans `.env` et configurez les URLs RTSP dans le Dashboard → ⚙️ Configuration.

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

**Samya** — IoT Industriel & Traçabilité Logistique
📍 Stage d'initiation — LafargeHolcim Meknès, Maroc
🔗 [github.com/samya818](https://github.com/samya818)

---

**Construit avec ❤️ pour une logistique industrielle plus intelligente**

*Si ce projet vous a aidé, n'hésitez pas à lui donner une ⭐ sur GitHub*
