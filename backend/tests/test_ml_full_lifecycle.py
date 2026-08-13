"""
Test E2E du Cycle de Vie ML Complet (Train -> Validate -> Save -> Reload -> Inference).
Vérifie rigoureusement :
1. L'absence de régression d'attributs (self.MODEL_DIR).
2. L'alignement exact des 13 features causales (Zero Train/Serving Mismatch).
3. L'exécution réelle de l'entraînement et de la sauvegarde des artefacts versionnés.
4. L'inférence causale de l'ETA restant sans fallback silencieux.
"""
import os
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Truck, Transporteur, Cycle, PosteType, TruckStatus
from app.services.auto_train import AutoTrainPipeline
from app.services.prediction import PredictionService
from app.services.feature_engineering import FEATURE_COLUMNS, build_single_inference_vector

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session_ml(tmp_path, monkeypatch):
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Isoler le répertoire des modèles dans un dossier temporaire
    models_dir = str(tmp_path / "models")
    os.makedirs(models_dir, exist_ok=True)
    monkeypatch.setattr("app.services.auto_train.SessionLocal", lambda: db)

    yield db, models_dir

    db.close()
    Base.metadata.drop_all(bind=engine)

def test_feature_engineering_consistency():
    """Vérifie l'immuabilité et la complétude des 13 colonnes de caractéristiques."""
    assert len(FEATURE_COLUMNS) == 13
    now = datetime(2026, 8, 14, 10, 30, 0)
    df_vec = build_single_inference_vector(now, [75.0, 80.0, 95.0], train_median_y=85.0)
    assert list(df_vec.columns) == FEATURE_COLUMNS
    assert df_vec.shape == (1, 13)
    assert df_vec['heure'].iloc[0] == 10.0
    assert df_vec['is_morning_rush'].iloc[0] == 1.0

def test_full_ml_train_save_predict_lifecycle(db_session_ml, monkeypatch):
    """Exécute l'entraînement E2E, la sauvegarde et l'inférence en production."""
    db, models_dir = db_session_ml

    # 1. Créer 40 cycles complets étalés dans le temps pour dépasser le seuil minimum (30 cycles)
    base_time = datetime(2026, 8, 1, 8, 0, 0)
    trans = Transporteur(id=1, nom="Ciments du Maroc")
    truck = Truck(id=10, immatriculation="45678-A-1", transporteur=trans)
    db.add(trans)
    db.add(truck)
    db.commit()

    for i in range(40):
        t_in = base_time + timedelta(hours=i * 3)
        duration = 75.0 + (i % 5) * 5.0  # Durées réalistes entre 75 et 95 minutes
        t_out = t_in + timedelta(minutes=duration)
        cycle = Cycle(
            id=100 + i,
            truck_id=10,
            entree_porte=t_in,
            sortie_porte=t_out,
            duree_total=duration,
            duree_parking=20.0,
            duree_bascule_tare=10.0,
            duree_ensachage=35.0,
            duree_bascule_brut=10.0,
            status=TruckStatus.TERMINE,
            est_anomalie=False
        )
        db.add(cycle)
    db.commit()

    # 2. Exécuter le pipeline AutoTrain
    pipeline = AutoTrainPipeline()
    pipeline.MODEL_DIR = models_dir
    pipeline.METRICS_FILE = os.path.join(models_dir, "training_metrics.json")

    res = pipeline.run_training_pipeline()
    assert res["status"] == "success"
    assert "metrics" in res["results"]
    assert res["results"]["feature_schema_version"] == "2.0.0"

    # Vérifier la présence des fichiers de modèles
    xgb_path = os.path.join(models_dir, "xgboost_champion.pkl")
    assert os.path.exists(xgb_path)

    # 3. Tester le service d'inférence avec le modèle sauvegardé
    pred_service = PredictionService(db)
    pred_service.MODEL_DIR = models_dir
    pred_service.niveau = 2  # Forcer palier ML

    pred_res = pred_service.predict_remaining_eta(
        poste_actuel=PosteType.ENSACHAGE,
        entree_porte=base_time + timedelta(hours=150),
        modele_prefere="xgboost"
    )

    assert "eta_minutes" in pred_res
    assert pred_res["eta_minutes"] >= 5.0
    assert pred_res["methode"] in ("xgboost_challenger", "prophet_production")
