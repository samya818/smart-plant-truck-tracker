# 📋 Backlog Technique & Roadmap d'Ingénierie Industrielle

Ce document consigne les chantiers de fiabilisation, de validation scientifique et de durcissement opérationnel pour la plateforme **Smart Plant Truck Tracker**.

---

## 🎯 1. Traçabilité Événementielle & Sémantique Temporelle (FSM)
- [x] **Idempotence Offline (`client_event_id`)** : UUID unique généré par la PWA et contrainte d'unicité en DB pour éviter les duplications lors des re-jeux réseau.
- [x] **Distinction Temporelle (`occurred_at` vs `received_at`)** : Calcul des durées de séjour basé sur l'heure réelle de constatation terrain et non sur l'heure d'ingestion serveur.
- [x] **Machine à États Finis (FSM)** : Validation formelle des transitions logistiques (`ARRIVED` $\rightarrow$ `PARKING` $\rightarrow$ `TARE` $\rightarrow$ `LOADING` $\rightarrow$ `GROSS` $\rightarrow$ `EXITED`) avec détection des sauts d'étapes.
- [x] **Qualification de la Précision GPS** : Stockage de `gps_accuracy_m` pour différencier les coordonnées précises des géolocalisations dégradées.

---

## 👁️ 2. Vision par Ordinateur & Modélisation Probabiliste
- [x] **Seuils de Décision à Deux Niveaux** :
  - `OCR_ACCEPT_THRESHOLD = 0.45` : Rejet des lectures corrompues (pur bruit).
  - `HUMAN_REVIEW_THRESHOLD = 0.65` : Transfert vers confirmation humaine mobile (`necesita_confirmacion = True`).
- [x] **Fuzzy Matching Durci & Détection d'Ambiguïté** : Seuil relevé à $0.85$ et alerte de collision si $\Delta(\text{Top1}, \text{Top2}) < 0.05$.
- [x] **Modélisation de Traçabilité Composite** : Formulation probabiliste rigoureuse de la tolérance de pannes : $\text{Taux} = 1 - (P(\text{échec vision}) \times P(\text{non-saisie agent}))$.
- [ ] **Benchmark Étendu Multi-Conditions** : Constitution d'un dataset calibré (100 images nettes, 100 poussière/clinker, 100 faible luminosité, 100 angles obliques) avec calcul de précision/rappel/F1-score.

---

## 🤖 3. MLOps & Prédiction Industrielle des Temps de Séjour
- [x] **Formulation Formelle de la Cible** : $y_t = t_{\text{out}} - t_{\text{in}}$ (durée totale en minutes).
- [x] **Prévention Stricte du Data Leakage** : Features strictement causales (`shift >= 1`) sans look-ahead bias.
- [x] **Validation Temporelle Hors-Échantillon (Out-Of-Time Split)** : Évaluation sur 80% passé / 20% futur sans mélange aléatoire.
- [x] **Garde de Non-Régression (Champion vs Challenger)** : Le modèle candidat n'est promu que si $\text{MAE}_{\text{candidat}} < \text{MAE}_{\text{champion}}$.
- [x] **Multi-Métriques Documentées** : Suivi conjoint MAE, RMSE et MAPE comparés à la baseline naïve EWMA.

---

## 🔒 4. Durcissement Docker & Sécurité Réseau (Hardening)
- [x] **Séparation Environnements Dev / Prod** :
  - `docker-compose.prod.yml` : Réseau interne isolé pour PostgreSQL et Redis, suppression d'Adminer, désactivation de `uvicorn --reload`.
  - `docker-compose.dev.yml` : Exposition des ports locaux pour inspection rapide et debug.
- [ ] **Passage en Production Critique (Checklist Hard Production)** :
  - Intégration d'un reverse-proxy Nginx avec terminaison TLS (HTTPS / WSS).
  - Gestion des secrets applicatifs via HashiCorp Vault ou KMS.
  - Mise en place d'une politique de rétention et purge automatique des photos caméras (`./uploads`).

---

## 🧪 5. Concurrence & Résilience Temps Réel
- [x] **Test de Race Condition (Concurrence Simultanée)** : Validation automatisée de la fusion hybride caméra/agent mobile sous charge parallèle (`test_concurrency_race.py`).
- [x] **Reconnexion WebSocket & Resynchronisation Active** : Reconnexion automatique avec backoff et réinterrogation immédiate de `GET /api/events/active` pour restaurer la vérité PostgreSQL.
- [ ] **Surveillance de la Santé Caméra (Health Monitoring)** : Transition d'un booléen statique vers une machine d'état runtime (`ONLINE`, `DEGRADED`, `OFFLINE`) avec compteur d'échecs consécutifs RTSP.
