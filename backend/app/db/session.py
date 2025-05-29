# backend/app/db/session.py
import time
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import sessionmaker
from ..core.config import settings

if settings.DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set in the environment or configuration.")

MAX_RETRIES = 10
RETRY_DELAY = 5 # seconds

def create_db_engine_with_retries():
    for attempt in range(MAX_RETRIES):
        try:
            assert settings.DATABASE_URL is not None, "DATABASE_URL cannot be None"
            engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
            # Try to establish a connection to check if DB is ready
            with engine.connect() as connection:
                print("Database connection successful.")
                return engine
        except exc.OperationalError as e:
            print(f"Database connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print("Max retries reached. Could not connect to the database.")
                raise
    # This line should ideally not be reached if MAX_RETRIES > 0
    # but as a fallback or if MAX_RETRIES is 0:
    raise exc.OperationalError("Could not connect to database after multiple retries or no retries configured.", params=None, orig=None) # type: ignore


engine = create_db_engine_with_retries()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency that provides a database session.
    It ensures the session is closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()