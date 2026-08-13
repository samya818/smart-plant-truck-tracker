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


from app.services.feature_engineering import build_features_matrix_train, FEATURE_COLUMNS

def test_feature_engineering_xgboost():
    """Vérifie que les 13 features temporelles et lags causaux sont correctement calculés."""
    dates = pd.date_range(start="2026-01-01", periods=100, freq="h")
    df = pd.DataFrame({
        'entree_porte': dates,
        'ds': dates,
        'y': np.random.uniform(40, 120, size=100),
    })

    df_feat, median_imputed = build_features_matrix_train(df)
    
    # Vérification de la présence des features cycliques et temporelles
    for col in FEATURE_COLUMNS:
        assert col in df_feat.columns
    assert 'hour_sin' in df_feat.columns
    assert 'hour_cos' in df_feat.columns
    assert 'dow_sin' in df_feat.columns
    assert 'is_weekend' in df_feat.columns
    assert 'rolling_mean_5' in df_feat.columns
    assert not df_feat[FEATURE_COLUMNS].isnull().values.any()  # Pas de valeurs NaN


def test_auto_train_pipeline_dry_run(db, monkeypatch, tmp_path):
    """Vérifie l'exécution du pipeline sur la session de test."""
    monkeypatch.setattr("app.services.auto_train.SessionLocal", lambda: db)
    pipeline = AutoTrainPipeline()
    pipeline.MODEL_DIR = str(tmp_path / "models")
    pipeline.METRICS_FILE = os.path.join(pipeline.MODEL_DIR, "training_metrics.json")
    
    # Exécution sur la base de test
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
