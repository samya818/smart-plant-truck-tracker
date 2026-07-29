# Fix: Incohérence KPI "Camions en cours" vs liste des camions actifs

## Problème
Le KPI "Camions en cours" (dashboard/stats) utilisait une logique événementielle alors que la liste des camions actifs (events/active) utilise la table `cycles`. Incohérence = KPI à 0 même avec 6 camions actifs.

## Étapes
- [x] Analyser le code et identifier la divergence
- [x] Corriger `camions_en_cours` dans `dashboard.py` (passer de Event → Cycle)
- [x] Corriger `alertes_actives` dans `dashboard.py` (passer de Event → Cycle)
- [x] Nettoyer l'import `and_` inutilisé
- [x] Redémarrer le backend
- [x] Vérifier la cohérence ✅ → `camions_en_cours: 6` (match avec les camions actifs)

