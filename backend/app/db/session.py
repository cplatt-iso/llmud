# backend/app/db/session.py
import time
import logging
from typing import Generator
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker
from ..core.config import settings

# Logger for this module
logger = logging.getLogger(__name__)

if settings.DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set in the environment or configuration.")

# The engine is now just a placeholder. It will be created and assigned during app startup.
engine = None
# The SessionLocal factory is created now, but it is not bound to any engine yet.
SessionLocal = sessionmaker(autocommit=False, autoflush=False)

MAX_RETRIES = 10
RETRY_DELAY = 5 # seconds

def create_db_engine_with_retries():
    """
    This function no longer assigns to a global variable. It just creates,
    tests, and returns a new database engine.
    """
    for attempt in range(MAX_RETRIES):
        try:
            assert settings.DATABASE_URL is not None, "DATABASE_URL cannot be None"
            created_engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)
            with created_engine.connect() as connection:
                logger.info("Database connection successful during creation.")
                return created_engine
        except exc.OperationalError as e:
            logger.warning(f"Database connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not connect to the database.")
                raise

    # This line should ideally not be reached, but as a fallback:
    # --- FIX IS HERE ---
    # This simpler raise statement accomplishes the same goal without upsetting Pylance.
    raise exc.OperationalError("Could not connect to database after multiple retries.")


def get_db() -> Generator:
    """
    FastAPI dependency that provides a database session.
    It now checks if the engine has been initialized and binds the engine
    to the session on-the-fly.
    """
    global engine
    if engine is None:
        raise RuntimeError("Database engine has not been initialized. The application lifespan manager may have failed.")
    
    # We create a new session and bind it to our globally managed engine
    db = SessionLocal(bind=engine)
    try:
        yield db
    finally:
        db.close()