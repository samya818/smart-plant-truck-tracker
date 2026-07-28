<div align="center">

# 🏭 Smart Plant Truck Tracker
### LafargeHolcim Meknès — Intelligent Logistics Platform

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791?style=for-the-badge&logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=for-the-badge&logo=docker)](https://docker.com)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=for-the-badge&logo=typescript)](https://typescriptlang.org)

> **Every minute a cement truck waits inside your plant is money lost.**
> This system tracks every truck, at every gate, at every second — automatically.

</div>

---

## 🎯 What Problem Does This Solve?

At a cement plant like **LafargeHolcim Meknès**, dozens of trucks enter and exit every day. Each truck passes through **4 critical zones**:

```
🚪 Entry Gate  →  🅿️ Parking  →  ⚖️ Weighbridge  →  📦 Loading Bay  →  🚪 Exit Gate
```

Without a tracking system, supervisors have **no visibility** over:
- How long has this truck been waiting?
- Which zone is creating bottlenecks today?
- Which transport company causes the most delays?
- Why was truck `45231-A-12` late last Tuesday?

**This platform answers all those questions — in real time.**

---

## ✨ Key Features

### 🖥️ Supervisor Dashboard
- **Live truck tracking** via WebSocket — no page refresh needed
- Visual timeline of each truck's journey through the plant
- Real-time alerts for trucks exceeding waiting time limits
- Camera URL configuration per zone (Bi-Mode: OCR Camera + Mobile Agent)

### 📊 Statistics & Analytics
- Filter by **Today / Last 7 Days / Last 30 Days**
- Cycle time analysis: average, median, min, max vs. 120-min target
- **Zone-by-zone delay breakdown** with threshold compliance charts
- **Full cause-of-delay analysis** with progress bars and % of global delay
- Transport company performance ranking with cumulative delay minutes
- Data source breakdown: OCR Camera vs. Mobile Agent vs. Hybrid

### 📱 Mobile Agent Interface
- Field agents can log truck entries/exits from their **smartphone**
- Optional photo capture of license plates
- GPS geolocation attached to every event
- Report delays with cause selection + free text comment
- Works as a **Progressive Web App (PWA)** — installable on any phone

### 🤖 Bi-Mode Capture System

| Mode | Description | Best For |
|------|-------------|----------|
| **Camera OCR** | AI reads the license plate automatically | Normal conditions |
| **Mobile Agent** | Human agent confirms/enters plate manually | Dusty conditions |
| **Hybrid** | Camera attempts first, agent validates if unsure | Maximum reliability |

---

## 🏗️ System Architecture

```mermaid
graph TB
    subgraph CLIENT["🌐 Client Layer"]
        DASH["🖥️ Supervisor Dashboard\n(React + Recharts)"]
        MOBILE["📱 Mobile Agent App\n(PWA - React)"]
    end

    subgraph GATEWAY["⚡ Real-Time Gateway"]
        WS["🔌 WebSocket Server\n/ws/live"]
        REST["🔗 REST API\nFastAPI"]
    end

    subgraph CORE["🧠 Core Services"]
        INGEST["📥 Event Ingestion\nService"]
        ANALYTICS["📊 Analytics\nEngine"]
        CV["👁️ CV Simulation\nService"]
    end

    subgraph DATA["💾 Data Layer"]
        PG[("🐘 PostgreSQL 16\nTrucks · Events · Cycles")]
        REDIS[("⚡ Redis\nPub/Sub Cache")]
        UPLOADS["📁 Photo Uploads\nLocal Storage"]
    end

    subgraph FIELD["🏭 Plant Field"]
        CAM1["📷 Gate Camera\nRTSP Stream"]
        CAM2["📷 Weighbridge Camera\nRTSP Stream"]
        CAM3["📷 Loading Bay Camera\nRTSP Stream"]
        AGENT["👷 Field Agent\nSmartphone"]
    end

    DASH -->|"HTTP + WS"| REST
    DASH <-->|"WebSocket"| WS
    MOBILE -->|"HTTP POST\nmultipart/form-data"| REST

    REST --> INGEST
    REST --> ANALYTICS
    WS <-->|"Pub/Sub"| REDIS

    INGEST --> PG
    INGEST -->|"Notify"| REDIS
    ANALYTICS --> PG
    CV --> INGEST

    CAM1 -->|"RTSP"| CV
    CAM2 -->|"RTSP"| CV
    CAM3 -->|"RTSP"| CV
    AGENT -->|"Photo + GPS"| REST

    MOBILE -->|"Store photo"| UPLOADS

    style CLIENT fill:#EFF6FF,stroke:#3B82F6
    style GATEWAY fill:#F0FDF4,stroke:#22C55E
    style CORE fill:#FFF7ED,stroke:#F97316
    style DATA fill:#FDF4FF,stroke:#A855F7
    style FIELD fill:#FFF1F2,stroke:#F43F5E
```

---

## 🔄 Full Truck Lifecycle — Step by Step

```mermaid
sequenceDiagram
    participant T as 🚛 Truck
    participant G as 🚪 Gate Camera / Agent
    participant API as ⚡ FastAPI
    participant DB as 🐘 PostgreSQL
    participant WS as 🔌 WebSocket
    participant S as 🖥️ Supervisor

    T->>G: Arrives at plant gate
    G->>API: POST /api/mobile/events plate + poste=porte_usine + type=entree
    API->>DB: Create Event + Open new Cycle
    API->>WS: Broadcast truck status update
    WS->>S: Live dashboard update (no refresh needed)

    T->>G: Arrives at Weighbridge (Tare)
    G->>API: POST event poste=bascule type=entree
    API->>DB: Update Cycle.duree_parking

    T->>G: Arrives at Loading Bay
    G->>API: POST event poste=ensachage type=entree
    API->>DB: Update Cycle.duree_bascule_tare

    Note over T,S: Loading takes up to 45 min (threshold)

    T->>G: Exits Loading Bay
    G->>API: POST event poste=ensachage type=sortie
    API->>DB: Update Cycle.duree_ensachage

    T->>G: Exits Plant Gate
    G->>API: POST event poste=porte_usine type=sortie
    API->>DB: Close Cycle — status=TERMINE duree_total=X min
    API->>WS: Truck completed broadcast
    WS->>S: Dashboard removes truck from active list
```

---

## 🗃️ Database Schema

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

    TRANSPORTEUR ||--o{ TRUCK : "owns"
    TRUCK ||--o{ EVENT : "generates"
    TRUCK ||--o{ CYCLE : "completes"
    EVENT }o--|| DELAY_CAUSE : "linked to"
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | React 18 + TypeScript | Fast, type-safe UI |
| **Charts** | Recharts | Beautiful, responsive data visualization |
| **Icons** | Lucide React | Clean, consistent icon set |
| **Styling** | Tailwind CSS | Rapid utility-first styling |
| **PWA** | Vite Plugin PWA | Mobile-installable, offline capable |
| **Backend** | FastAPI (Python) | Async, auto-documented REST API |
| **ORM** | SQLAlchemy 2 | Safe, powerful database queries |
| **Database** | PostgreSQL 16 | Reliable relational data storage |
| **Cache/Events** | Redis 7 | Real-time pub/sub broadcasting |
| **Real-Time** | WebSocket | Instant dashboard updates |
| **Deployment** | Docker Compose | One-command full stack launch |
| **Web Server** | Nginx (Alpine) | Lightweight static file serving |

---

## 🚀 Quick Start — Run in 3 Commands

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Git](https://git-scm.com/) installed

### Installation

```bash
# 1. Clone the project
git clone https://github.com/samya818/smart-plant-truck-tracker.git
cd smart-plant-truck-tracker

# 2. Create environment file
cp .env.example .env

# 3. Build and launch everything
docker compose up -d --build
```

> ✅ That's it. All 5 services start automatically.

### Access the Application

| Interface | URL | Description |
|-----------|-----|-------------|
| 🖥️ **Supervisor Dashboard** | http://localhost | Main monitoring screen |
| 📊 **Statistics** | http://localhost/statistiques | Analytics & reports |
| 📱 **Mobile Agent** | http://localhost/mobile | Field agent interface |
| 🔧 **API Documentation** | http://localhost:8000/docs | Interactive API explorer |
| 🗄️ **Database Admin** | http://localhost:8080 | Adminer (DB browser) |

---

## 📁 Project Structure

```
smart-plant-truck-tracker/
│
├── 📂 backend/
│   └── app/
│       ├── main.py               # App entry point + startup seeding
│       ├── models.py             # SQLAlchemy database models
│       ├── schemas.py            # Pydantic request/response schemas
│       ├── config.py             # Settings & environment variables
│       ├── routers/
│       │   ├── analytics.py      # Statistics & reporting endpoints
│       │   ├── dashboard.py      # Live dashboard data
│       │   ├── mobile.py         # Mobile agent endpoints
│       │   └── events.py         # Event history
│       └── services/
│           ├── event_ingestion.py # Core business logic: cycle tracking
│           └── cv_service.py      # Camera simulation / OCR service
│
├── 📂 frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx          # Supervisor dashboard
│       │   ├── StatistiquesPage.tsx   # Analytics & statistics
│       │   └── MobilePage.tsx         # Mobile agent interface
│       ├── components/
│       │   ├── TruckCard.tsx          # Truck status card
│       │   ├── StatsChart.tsx         # Statistics charts
│       │   └── mobile/
│       │       └── AgentCapture.tsx   # Mobile capture form
│       ├── hooks/
│       │   ├── useWebSocket.ts        # WebSocket connection hook
│       │   └── useCamera.ts           # Camera capture hook
│       └── services/api.ts            # API call functions
│
├── docker-compose.yml
└── .env.example
```

---

## ⚙️ Environment Variables

```env
# Database
POSTGRES_USER=lafarge_user
POSTGRES_PASSWORD=your_strong_password
POSTGRES_DB=lafarge_tracker

# Application mode
CV_MODE=simulation          # "simulation" or "real"
SIMULATION_TRUCKS_PER_DAY=80

# Thresholds (minutes)
SEUIL_ATTENTE_PARKING_MAX=30
SEUIL_BASCULE_MAX=15
SEUIL_ENSACHAGE_MAX=45
SEUIL_CYCLE_TOTAL_MAX=120
```

---

## 🎬 How the Simulation Works

When `CV_MODE=simulation`, the backend automatically generates realistic truck traffic:

- **80 trucks/day** by default (configurable)
- Trucks arrive between **06:00 and 18:00**
- Each truck goes through all 4 zones with realistic durations
- Random delays and anomalies are injected (~15% of cycles)
- The dashboard updates live as trucks complete their journeys

> **This lets you test the full system without any physical cameras.**

To use real cameras, set `CV_MODE=real` in `.env` and configure RTSP URLs in the Dashboard → ⚙️ Configuration panel.

---

## 📈 Business Value

| Metric | Before | After |
|--------|--------|-------|
| Cycle visibility | ❌ None | ✅ Real-time per truck |
| Bottleneck detection | ❌ End-of-day report | ✅ Instant alert |
| Delay accountability | ❌ No data | ✅ Per carrier, per cause |
| Agent reporting | ❌ Paper forms | ✅ Smartphone in 10 seconds |
| Monthly statistics | ❌ Manual Excel | ✅ Auto-generated with charts |

---

## 👤 Author

**Samya** — Industrial IoT & Logistics Tracking
📍 LafargeHolcim Meknès, Morocco
🔗 [github.com/samya818](https://github.com/samya818)

---

<div align="center">

**Built with ❤️ for smarter industrial logistics**

*If this project helped you, consider giving it a ⭐ on GitHub*

</div>
