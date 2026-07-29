# ============================================================
# LAFARGE CAMION TRACKER — Script de déploiement
# ============================================================
# Ce script configure automatiquement l'application pour 
# l'environnement de l'usine LafargeHolcim Meknès.
#
# ⚠️ À exécuter VOLONTAIREMENT après git clone
#    Ne s'exécute PAS automatiquement
#
# Usage : .\setup-lafarge.ps1
# ============================================================

Write-Host "🚀 Déploiement Lafarge Camion Tracker" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. Vérifier que Docker Desktop est lancé
Write-Host "🔍 Vérification de Docker Desktop..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "✅ Docker Desktop est actif" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Desktop n'est pas lancé !" -ForegroundColor Red
    Write-Host "   Veuillez démarrer Docker Desktop et réessayer." -ForegroundColor Red
    exit 1
}

# 2. Trouver l'IP du PC serveur
Write-Host "🔍 Détection de l'IP du serveur..." -ForegroundColor Yellow
$IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.InterfaceAlias -like "*Wi-Fi*" -or $_.InterfaceAlias -like "*Ethernet*" 
} | Select-Object -First 1).IPAddress

if (-not $IP) {
    Write-Host "❌ Impossible de détecter l'IP réseau" -ForegroundColor Red
    Write-Host "   Veuillez entrer l'IP manuellement dans le fichier .env" -ForegroundColor Red
    exit 1
}

Write-Host "✅ IP détectée : $IP" -ForegroundColor Green
Write-Host ""

# 3. Désactiver la simulation
Write-Host "🔧 Configuration du mode production..." -ForegroundColor Yellow
$configPath = "backend/app/config.py"
if (Test-Path $configPath) {
    (Get-Content $configPath) -replace 'cv_mode: str = "simulation"', 'cv_mode: str = "real"' | Set-Content $configPath
    Write-Host "✅ Simulation désactivée (mode = real)" -ForegroundColor Green
} else {
    Write-Host "⚠️ Fichier config.py non trouvé" -ForegroundColor Yellow
}

# 4. Créer le .env du frontend
Write-Host "🔧 Configuration du frontend..." -ForegroundColor Yellow
$envContent = @"
# Configuration automatique pour l'usine Lafarge
# IP détectée : $IP
VITE_API_BASE_URL=http://$IP`:8000
"@
$envContent | Set-Content "frontend/.env" -Encoding UTF8
Write-Host "✅ Frontend configuré avec l'IP $IP" -ForegroundColor Green

# 5. Modifier le CORS du backend
Write-Host "🔧 Configuration CORS..." -ForegroundColor Yellow
$mainPath = "backend/app/main.py"
if (Test-Path $mainPath) {
    $content = Get-Content $mainPath -Raw
    
    # Vérifier si CORS existe déjà
    if ($content -match "allow_origins=") {
        # Remplacer les IPs existantes par la nouvelle
        $newContent = $content -replace '"http://192\.168\.\d+\.\d+"', "`"http://$IP`""
        $newContent = $newContent -replace '"http://192\.168\.\d+\.\d+:80"', "`"http://$IP`:80`""
        $newContent = $newContent -replace '"http://192\.168\.\d+\.\d+:8000"', "`"http://$IP`:8000`""
        $newContent | Set-Content $mainPath -Encoding UTF8
        Write-Host "✅ CORS mis à jour avec l'IP $IP" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Configuration CORS non trouvée dans main.py" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "🔨 Build et démarrage des conteneurs..." -ForegroundColor Yellow
docker compose down
docker compose up -d --build

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "✅ Déploiement terminé !" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Dashboard superviseur : http://$IP" -ForegroundColor Cyan
Write-Host "📱 Interface agent mobile : http://$IP/mobile" -ForegroundColor Cyan
Write-Host "📚 Documentation API : http://$IP:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️ Prochaines étapes :" -ForegroundColor Yellow
Write-Host "   1. Configurer les URLs des caméras RTSP dans le Dashboard" -ForegroundColor White
Write-Host "   2. Tester la connexion aux caméras" -ForegroundColor White
Write-Host "   3. Former les agents à l'interface mobile" -ForegroundColor White
Write-Host ""