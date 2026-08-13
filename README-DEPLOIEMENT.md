

# 🚀 Guide de Déploiement — Lafarge Camion Tracker

## Prérequis

- PC Windows 10/11 avec 8 GB RAM minimum
- Docker Desktop installé et lancé
- Accès réseau aux caméras IP de l'usine
- Connexion Internet (pour télécharger les images Docker)

## Installation & Déploiement Rapide

### Étape 1 : Cloner le projet

```powershell
git clone https://github.com/samya818/smart-plant-truck-tracker.git
cd smart-plant-truck-tracker
```

### Étape 2 : Exécuter le script de déploiement

```powershell
.\setup-lafarge.ps1
```

Ce script configure automatiquement :
- ✅ Désactivation de la simulation
- ✅ Détection de l'IP du serveur
- ✅ Configuration du frontend
- ✅ Configuration CORS
- ✅ Build et démarrage Docker

### Étape 3 : Configurer les caméras

1. Ouvrir le Dashboard : `http://IP_DU_PC`
2. Aller dans "⚙️ Configuration des Postes (Bi-Mode)"
3. Saisir les URLs RTSP des caméras :
   - Porte Usine : `rtsp://admin:pass@192.168.1.50:554/stream`
   - Parking : `rtsp://admin:pass@192.168.1.51:554/stream`
   - Bascule : `rtsp://admin:pass@192.168.1.52:554/stream`
   - Ensachage : `rtsp://admin:pass@192.168.1.53:554/stream`

### Étape 4 : Tester

- Dashboard : `http://IP_DU_PC`
- Interface mobile (agents) : `http://IP_DU_PC/mobile`

## Accès Agents

Les agents se connectent au WiFi de l'usine et ouvrent :
```
http://IP_DU_PC/mobile
```

Sur leur téléphone, ils peuvent :
- Saisir les plaques d'immatriculation
- Prendre des photos
- Signaler des retards
- Voir les camions en cours

## Support

En cas de problème :
1. Vérifier que Docker Desktop est lancé
2. Vérifier les logs : `docker logs lafarge_backend --tail 50`
3. Redémarrer : `docker compose restart`
```
