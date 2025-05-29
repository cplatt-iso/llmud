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
    
    DATABASE_URL: Optional[str] = "postgresql://dummy_user:dummy_password@dummy_host:5432/dummy_db" if IS_ALEMBIC_ENV_PY_CONTEXT else None
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7" # CHANGE THIS IN PRODUCTION!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # Token expires in 7 days

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

settings = Settings() 

# After instantiation, if it was a dummy, ensure it's overridden if not in Alembic context
# and the real env var is available. This is getting complex.
if IS_ALEMBIC_ENV_PY_CONTEXT and settings.DATABASE_URL is not None and settings.DATABASE_URL.startswith("postgresql://dummy_user"):
    print("INFO: Settings initialized with dummy DATABASE_URL for Alembic env.py import phase.")
elif settings.DATABASE_URL is not None and not settings.DATABASE_URL.startswith("postgresql://dummy_user") and os.getenv("DATABASE_URL"):
     # This would be the normal app run, where env var should override any default
     pass
elif not IS_ALEMBIC_ENV_PY_CONTEXT and not os.getenv("DATABASE_URL"):
    # This will have already failed in Settings() if '...' was used and no env var
    print("WARNING: DATABASE_URL not found in environment for normal app run!")