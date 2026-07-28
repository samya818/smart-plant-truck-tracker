#!/bin/bash
# ============================================================
# start.sh — Point d'entrée du conteneur backend
# 1. Attend que PostgreSQL soit prêt
# 2. Lance `alembic upgrade head` (migrations automatiques)
# 3. Démarre uvicorn
# ============================================================
set -e

echo "⏳ Attente de PostgreSQL..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        host=os.getenv('POSTGRES_HOST','db'),
        port=os.getenv('POSTGRES_PORT', 5432),
        dbname=os.getenv('POSTGRES_DB','lafarge_tracker'),
        user=os.getenv('POSTGRES_USER','lafarge_user'),
        password=os.getenv('POSTGRES_PASSWORD','change_me_strong_password'),
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    sleep 1
    echo "  → PostgreSQL pas encore prêt, nouvelle tentative..."
done

echo "✅ PostgreSQL prêt."

echo "🔄 Application des migrations Alembic..."
alembic upgrade head
echo "✅ Migrations appliquées."

echo "🚀 Démarrage du serveur uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
