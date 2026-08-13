#!/bin/bash
# ==============================================================================
# SMART TRUCK TRACKER — Script de Déploiement Industriel (Linux / Ubuntu Server)
# ==============================================================================
# Usage : chmod +x deploy.sh && ./deploy.sh
# ==============================================================================

set -e

echo -e "\033[1;36m=================================================================\033[0m"
echo -e "\033[1;36m🚀 DÉPLOIEMENT INDUSTRIEL — SMART PLANT TRUCK TRACKER           \033[0m"
echo -e "\033[1;36m=================================================================\033[0m"

# 1. Vérification de Docker et Docker Compose
echo -e "\n\033[1;33m🔍 1. Vérification de l'environnement Docker...\033[0m"
if ! command -v docker &> /dev/null; then
    echo -e "\033[1;31m❌ Docker n'est pas installé sur ce serveur.\033[0m"
    echo "Installez Docker : https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "\033[1;31m❌ Docker Compose v2 n'est pas disponible.\033[0m"
    exit 1
fi
echo -e "\033[1;32m✅ Moteur Docker opérationnel.\033[0m"

# 2. Configuration du fichier d'environnement .env
echo -e "\n\033[1;33m⚙️ 2. Configuration des variables d'environnement (.env)...\033[0m"
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "\033[1;32m✅ Fichier .env créé à partir de .env.example\033[0m"
fi

# Activer le mode réel (caméras IP) au lieu de la simulation
sed -i 's/CV_MODE=.*/CV_MODE=real/' .env || true
echo -e "\033[1;32m✅ Mode opérationnel usine configuré (CV_MODE=real)\033[0m"

# 3. Création des répertoires de données persistantes
echo -e "\n\033[1;33m📁 3. Préparation des volumes et répertoires de stockage...\033[0m"
mkdir -p uploads models backend/uploads
chmod -R 775 uploads models

# 4. Construction et démarrage des conteneurs
echo -e "\n\033[1;33m🐳 4. Construction et lancement de la stack conteneurisée...\033[0m"
docker compose down || true
docker compose up -d --build

# 5. Vérification de santé des services
echo -e "\n\033[1;33m🩺 5. Validation de la santé des conteneurs...\033[0m"
sleep 5
docker compose ps

# Récupération de l'adresse IP du serveur
SERVER_IP=$(hostname -I | awk '{print $1}')

echo -e "\n\033[1;32m=================================================================\033[0m"
echo -e "\033[1;32m🎉 DÉPLOIEMENT TERMINÉ AVEC SUCCÈS !\033[0m"
echo -e "\033[1;32m=================================================================\033[0m"
echo -e "🖥️  Dashboard Superviseur : \033[1;34mhttp://${SERVER_IP}\033[0m (ou http://localhost)"
echo -e "📱 Interface Agent Mobile : \033[1;34mhttp://${SERVER_IP}/mobile\033[0m"
echo -e "📊 Statistiques & KPIs    : \033[1;34mhttp://${SERVER_IP}/statistiques\033[0m"
echo -e "📖 Documentation API      : \033[1;34mhttp://${SERVER_IP}:8000/docs\033[0m"
echo -e "🗄️  Gestionnaire Base      : \033[1;34mhttp://${SERVER_IP}:8080\033[0m"
echo -e "\033[1;32m=================================================================\033[0m\n"
