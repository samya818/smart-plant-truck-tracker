# ============================================================
# Commandes Alembic — À exécuter depuis le conteneur backend
# ============================================================
#
# GÉNÉRER une nouvelle migration automatiquement :
#   docker exec lafarge_backend alembic revision --autogenerate -m "description_courte"
#
# APPLIQUER toutes les migrations en attente :
#   docker exec lafarge_backend alembic upgrade head
#
# VOIR le statut actuel :
#   docker exec lafarge_backend alembic current
#
# VOIR l'historique des migrations :
#   docker exec lafarge_backend alembic history --verbose
#
# ROLLBACK d'une migration :
#   docker exec lafarge_backend alembic downgrade -1
#
# ============================================================
# WORKFLOW RECOMMANDÉ POUR CHAQUE MODIFICATION DU MODÈLE :
# ============================================================
#
#  1. Modifier app/models.py (ajouter colonne, table, etc.)
#
#  2. Générer la migration :
#     docker exec lafarge_backend alembic revision --autogenerate -m "ajout_colonne_xxx"
#
#  3. Vérifier le fichier généré dans alembic/versions/
#     (toujours relire avant d'appliquer !)
#
#  4. Appliquer :
#     docker exec lafarge_backend alembic upgrade head
#
#  5. Committer les fichiers :
#     git add backend/alembic/versions/
#     git commit -m "migration: ajout_colonne_xxx"
#
# ============================================================
