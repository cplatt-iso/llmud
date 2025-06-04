# backend/app/core/config.py
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Check if we're likely running in an Alembic 'env.py' context BEFORE settings are needed for DB connection
# This is a heuristic. Alembic sets 'alembic.version' in its context.
# A simpler heuristic: if a specific env var for alembic is set.
IS_ALEMBIC_ENV_PY_CONTEXT = os.getenv("ALEMBIC_ENV_PY_RUNNING") == "true"

class Settings(BaseSettings):
    PROJECT_NAME: str = "MUD Project - Backend"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: Optional[str] = "postgresql://dummy_user:dummy_password@dummy_host:5432/dummy_db" if IS_ALEMBIC_ENV_PY_CONTEXT else os.getenv("DATABASE_URL", "postgresql://user:password@db/llmud_db") # Added os.getenv for normal case
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7" # CHANGE THIS IN PRODUCTION!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # Token expires in 7 days

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper() # Default to INFO
    SHOW_COMBAT_ROLLS_TO_PLAYER: bool = os.getenv("SHOW_COMBAT_ROLLS_TO_PLAYER", "True").lower() == "true"


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings() 

# After instantiation, if it was a dummy, ensure it's overridden if not in Alembic context
# and the real env var is available.
if IS_ALEMBIC_ENV_PY_CONTEXT and settings.DATABASE_URL is not None and "dummy_user" in settings.DATABASE_URL:
    # logger.info("Settings initialized with dummy DATABASE_URL for Alembic env.py import phase.") # Can't use logger before setup
    print("INFO: Settings initialized with dummy DATABASE_URL for Alembic env.py import phase.")
elif not IS_ALEMBIC_ENV_PY_CONTEXT and os.getenv("DATABASE_URL"):
    settings.DATABASE_URL = os.getenv("DATABASE_URL") # Ensure it's set from env if not in alembic context
elif not IS_ALEMBIC_ENV_PY_CONTEXT and not os.getenv("DATABASE_URL"):
    # This will have already failed in Settings() if '...' was used and no env var
    # logger.warning("DATABASE_URL not found in environment for normal app run!") # Can't use logger before setup
    print("WARNING: DATABASE_URL not found in environment for normal app run!")