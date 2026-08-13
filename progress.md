# 📊 Suivi de Progression — Stage LafargeHolcim Meknès

## Semaine 1 : Fondations
- [ ] Setup environnement (Python 3.11.9, Node 20, Docker)
- [ ] Architecture + Git init
- [ ] Modélisation DB V2 (PosteConfig, DelayCause, Event.source)
- [ ] API CRUD basique + router mobile
- [ ] Simulation 30 jours de données (logique de cycle respectée)

## Semaine 2 : Ingestion Bi-Mode & Backend Core
- [ ] EventIngestionService (point d'entrée unique)
- [ ] YOLOv8 + EasyOCR (mode simulation par défaut)
- [ ] Logique entrée/sortie par poste avec déduplication
- [ ] WebSocket temps réel (ou polling HTTP fallback)
- [ ] Calcul durées cycle (parking, bascule, ensachage)

## Semaine 3 : Dashboard & PWA Mobile
- [ ] React + TypeScript + Tailwind
- [ ] Dashboard temps réel (liste + barres de progression)
- [ ] Dashboard historique (Recharts) + Top 5 causes retard
- [ ] PWA Agent Mobile (scan photo, formulaire retard, causes dynamiques)
- [ ] Mode offline basique (file d'attente requêtes)

## Semaine 4 : Intelligence & Analytics
- [ ] Niveau 0 : Règles métier opérationnelles
- [ ] Niveau 1 : EWMA + Z-score
- [ ] Niveau 2 : Prophet (production) + toggle XGBoost (expérimental)
- [ ] Analyse horaire/journalière + Heatmap congestion
- [ ] Graphique Pareto des causes de retard

## Semaine 5 : MLOps & Finalisation
- [ ] Pipeline auto-entraînement (CRON) — Prophet prioritaire
- [ ] Docker Compose complet avec volume uploads/
- [ ] Tests + documentation
- [ ] Déploiement test en usine
- [ ] Soutenance

## Notes
- Modifier RTSP caméras avec OpenCV (si mode real activé)
- Demander accès tickets de pesée pour calibration
- Tester YOLOv8n vs yolov8s sur CPU usine
- **Important** : XGBoost est en mode expérimental uniquement
