# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os # <<< Import os

# We have to import the REAL app and settings to modify them
from app.main import app
from app.core.config import settings
from app.db.base_class import Base

# --- TEST DATABASE URL ---
# This is the in-memory database we'll use for all tests.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

# --- THE ONE AND ONLY FIXTURE WE NEED ---
@pytest.fixture(scope="session")
def test_client_with_db():
    """
    A fixture that provides a TestClient with a fully configured,
    in-memory SQLite database for the entire test session.
    """
    
    # --- 1. Monkeypatch the settings BEFORE the app starts ---
    # We are forcibly overriding the DATABASE_URL that the lifespan will use.
    # This is the key to the whole damn thing.
    settings.DATABASE_URL = SQLALCHEMY_DATABASE_URL
    
    # --- 2. Create the test database engine using the overridden URL ---
    # We must use StaticPool for in-memory SQLite to work with FastAPI.
    engine = create_engine(
        str(settings.DATABASE_URL), # Use the now-overridden setting
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    
    # --- 3. Create the tables in the test database ---
    # This happens once per test session.
    Base.metadata.create_all(bind=engine)
    
    # --- 4. Yield the properly configured TestClient ---
    # The app will now start up using our in-memory SQLite database.
    with TestClient(app) as client:
        yield client
        
    # --- 5. Teardown (not strictly necessary for in-memory, but good practice) ---
    Base.metadata.drop_all(bind=engine)