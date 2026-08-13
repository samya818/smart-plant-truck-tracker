"""
Configuration globale Pytest — Fixtures SQLite avec StaticPool & Isolation par Transaction.
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Forcer les variables d'environnement de test
os.environ["SIM_SPEED_MULTIPLIER"] = "1.0"
os.environ["REDIS_HOST"] = "localhost"

from app.models import Base
from app.database import get_db
from app.main import app

@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(autouse=True)
def override_db(db):
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    return TestClient(app)
