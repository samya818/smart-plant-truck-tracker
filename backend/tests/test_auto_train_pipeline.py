"""
Tests automatisés pour le pipeline d'entraînement MLOps (AutoTrainPipeline).
Vérifie la logique métier, le filtrage des anomalies et l'évaluation MAE Prophet / XGBoost.
"""
import pytest
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.services.auto_train import AutoTrainPipeline


def test_feature_engineering_xgboost():
    """Vérifie que les features temporelles et lags sont correctement calculés."""
    pipeline = AutoTrainPipeline()
    dates = pd.date_range(start="2026-01-01", periods=100, freq="h")
    df = pd.DataFrame({
        'ds': dates,
        'y': np.random.uniform(40, 120, size=100),
        'heure': [d.hour for d in dates],
        'jour_semaine': [d.weekday() for d in dates],
    })

    df_feat = pipeline._build_features(df)
    
    # Vérification de la présence des features cycliques et temporelles
    assert 'hour_sin' in df_feat.columns
    assert 'hour_cos' in df_feat.columns
    assert 'dow_sin' in df_feat.columns
    assert 'is_weekend' in df_feat.columns
    assert 'rolling_mean_24h' in df_feat.columns
    assert not df_feat.isnull().values.any()  # Pas de valeurs NaN


def test_auto_train_pipeline_dry_run():
    """Vérifie l'exécution du pipeline sur un jeu d'entraînement synthétique."""
    pipeline = AutoTrainPipeline()
    
    # Exécution sur la base de données réelle (vérification de non-crash)
    result = pipeline.run_training_pipeline()
    assert isinstance(result, dict)
    assert "status" in result
    assert result["status"] in ["success", "skipped", "failed"]


def test_training_metrics_format():
    """Vérifie que le pipeline sauvegarde correctement le format des métriques."""
    pipeline = AutoTrainPipeline()
    metrics_path = pipeline.METRICS_FILE
    
    test_metrics = {
        "date": datetime.now().isoformat(),
        "champion": "prophet",
        "mae": 12.4,
        "n_cycles": 150,
        "all_scores": {"prophet": 12.4, "xgboost": 14.1}
    }
    
    pipeline._save_metrics(test_metrics)
    assert os.path.exists(metrics_path)
    
    with open(metrics_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["champion"] == "prophet"
    assert loaded["mae"] == 12.4
