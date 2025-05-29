# backend/alembic/env.py
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# This line makes the 'app' directory available for import
# Ensure this path is correct relative to your alembic/env.py file.
# If env.py is in backend/alembic/, and your app is in backend/app/, then '..' goes to backend/
# and 'app' is the package.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))


from app.db.base_class import Base
from app.models.room import Room
from app.models.player import Player
from app.models.character import Character

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url() -> str | None:
    db_url_env = os.getenv("DB_URL") # This should be your primary source
    if db_url_env:
        print(f"DEBUG: get_url() found DB_URL from environment: {db_url_env}") # Add debug
        return db_url_env
    
    # This part will now read the placeholder from alembic.ini
    # It should only be reached if DB_URL env var is NOT set.
    ini_url = config.get_main_option("sqlalchemy.url")
    print(f"DEBUG: get_url() fell back to alembic.ini sqlalchemy.url: {ini_url}") # Add debug
    if ini_url == "PLEASE_SET_DB_URL_ENV_VAR": # Or whatever placeholder you used
         print("DEBUG: Placeholder URL found, indicating DB_URL env var was not set as expected.")
         return None # Or raise an error immediately
    return ini_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    if url is None: # Crucial check for None
        raise ValueError(
            "Database URL not found for offline migration. "
            "Set DB_URL environment variable or sqlalchemy.url in alembic.ini."
        )
        
    context.configure(
        url=url, # url is now guaranteed to be a str
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # Get the Alembic configuration section for database settings.
    # config.config_ini_section IS THE STRING NAME of the main section (e.g., "alembic")
    # config.get_section() takes this string name.
    db_config_section_dict = config.get_section(config.config_ini_section) # Use config.config_ini_section

    if db_config_section_dict is None:
        # This indicates a problem with alembic.ini or how config_ini_section is determined
        raise ValueError(
            f"Alembic configuration section '{config.config_ini_section}' " # CORRECTED: Use config.config_ini_section
            "not found in alembic.ini. Cannot configure database for online migrations."
        )

    # Get the database URL.
    db_url = get_url()
    if db_url is None: # Crucial check for None
        raise ValueError(
            "Database URL not found for online migration. "
            "Set DB_URL environment variable or sqlalchemy.url in alembic.ini."
        )

    # Update the configuration dictionary (which is now known not to be None)
    # with the resolved database URL.
    db_config_section_dict['sqlalchemy.url'] = db_url # db_url is now guaranteed str

    connectable = engine_from_config(
        db_config_section_dict, # This is now guaranteed to be Dict[str, str]
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

# Ensure either offline or online mode is selected by Alembic
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()