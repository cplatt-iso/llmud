# backend/app/main.py

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Setup Logging First ---
# This is correctly placed at the top.
try:
    from app.core.logging_config import setup_logging

    setup_logging()
except ImportError as e_log_setup:
    print(
        f"--- CRITICAL: main.py - FAILED to import or run setup_logging: {e_log_setup} ---",
        flush=True,
    )
    sys.exit(1)

# Get a logger for this module *after* setup is complete.
logger = logging.getLogger(__name__)

from app.api.v1.api_router import api_router as v1_api_router

# --- Module Imports ---
# These are now just declarations; they don't *do* anything on import anymore.
from app.core.config import settings
from app.crud.crud_character_class import seed_initial_character_class_templates
from app.crud.crud_item import seed_initial_items
from app.crud.crud_mob import seed_initial_mob_templates
from app.crud.crud_mob_spawn_definition import seed_initial_mob_spawn_definitions
from app.crud.crud_npc import seed_initial_npc_templates
from app.crud.crud_room import seed_initial_world
from app.crud.crud_skill import seed_initial_skill_templates
from app.crud.crud_trait import seed_initial_trait_templates
from app.db import base_class
from app.db import session as db_session  # <-- Import the session module itself
from app.game_logic.combat.combat_ticker import (
    start_combat_ticker_task,
    stop_combat_ticker_task,
)
from app.game_logic.npc_dialogue_ticker import (
    start_dialogue_ticker_task,
    stop_dialogue_ticker_task,
)
from app.game_logic.world_ticker import start_world_ticker_task, stop_world_ticker_task
from app.websocket_router import router as ws_router


# --- THE NEW LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("--- Application Startup Initiated ---")

    # 1. Initialize Database Engine
    logger.info("Initializing database engine...")
    db_session.engine = db_session.create_db_engine_with_retries()
    if db_session.engine is None:
        logger.critical("Failed to create database engine. Shutting down.")
        sys.exit(1)

    logger.info("Binding database engine to SessionLocal factory...")
    db_session.SessionLocal.configure(bind=db_session.engine)
    logger.info("SessionLocal factory configured.")

    # 2. Create Database Tables
    logger.info("Creating database tables...")
    try:
        base_class.Base.metadata.create_all(bind=db_session.engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.critical(f"Error creating database tables: {e}", exc_info=True)
        sys.exit(1)

    # 3. Seed Initial Data
    logger.info("Seeding initial data...")
    with db_session.SessionLocal() as db:
        try:
            # The order of seeding matters!
            seed_initial_items(db)
            seed_initial_world(db)
            seed_initial_mob_templates(db)
            seed_initial_npc_templates(db)
            seed_initial_character_class_templates(db)
            seed_initial_skill_templates(db)
            seed_initial_trait_templates(db)
            seed_initial_mob_spawn_definitions(db)
            logger.info("All data seeding completed successfully.")
        except Exception as e:
            logger.error(f"Error during data seeding: {e}", exc_info=True)
            # Decide if this is a critical failure that should stop startup
        finally:
            db.close()  # Ensure the session from get_db is closed

    # 4. Start Background Tasks
    logger.info("Starting background tasks...")
    start_world_ticker_task()
    start_combat_ticker_task()
    start_dialogue_ticker_task()
    logger.info("All background tasks started.")

    logger.info("--- Application Startup Complete ---")

    yield  # The application is now running and accepting requests

    # --- SHUTDOWN ---
    logger.info("--- Application Shutdown Initiated ---")
    stop_dialogue_ticker_task()
    stop_combat_ticker_task()
    stop_world_ticker_task()
    logger.info("Background tasks stopped.")

    if db_session.engine:
        db_session.engine.dispose()
        logger.info("Database engine disposed.")
    logger.info("--- Application Shutdown Complete ---")


# --- FASTAPI APP INITIALIZATION ---
# We now pass our lifespan manager to the FastAPI instance.
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
logger.info("FastAPI app instance created with lifespan manager.")

# --- MIDDLEWARE ---
origins = [
    "http://localhost:5174",
    "http://192.168.88.115:5174",
    "https://llmud.trazen.org",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTERS ---
app.include_router(v1_api_router, prefix=settings.API_V1_STR)
app.include_router(ws_router)
logger.info("API and WebSocket routers included.")


# --- ROOT ENDPOINT ---
@app.get("/")
async def root():
    logger.debug("GET / request received.")
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}. Now with a World Ticker humming in the background!"
    }


logger.info("--- main.py configuration complete. Application is ready to run. ---")
