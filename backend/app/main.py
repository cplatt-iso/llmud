# backend/app/main.py
import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import sys # For detailed print statements
from app.core.config import settings
import logging # Import logging
from fastapi.middleware.cors import CORSMiddleware 

# --- Setup Logging First ---
# This needs to happen before other modules that might use logging are imported,
# or at least before they try to log.
try:
    from app.core.logging_config import setup_logging
    setup_logging()
    print("--- MAIN.PY: setup_logging() CALLED (no exception caught) ---", flush=True)
except ImportError as e_log_setup:
    print(f"--- CRITICAL: main.py - FAILED to import or run setup_logging: {e_log_setup} ---", flush=True)
    sys.exit(1) # Exit if logging can't be set up, as it's crucial for debugging

logger = logging.getLogger(__name__) # Get a logger for this module

# --- Add these lines for immediate feedback on logger level ---
print(f"--- MAIN.PY: settings.LOG_LEVEL = '{settings.LOG_LEVEL}' ---", flush=True)
effective_level_main = logger.getEffectiveLevel()
print(f"--- MAIN.PY: Effective log level for 'app.main' logger = {effective_level_main} ({logging.getLevelName(effective_level_main)}) ---", flush=True)
logger.debug(f"--- MAIN.PY DEBUG LOG TEST: Top of file, Python version: {sys.version} ---") # Changed from logger.debug to ensure it prints if DEBUG is working
logger.info(f"--- MAIN.PY INFO LOG TEST: Top of file, Python version: {sys.version} ---")
# --- End of added lines ---

from app.api.v1.api_router import api_router as v1_api_router
logger.debug("--- main.py - Imported v1_api_router ---")
from app.websocket_router import router as ws_router
logger.debug("--- main.py - Imported ws_router ---")
from app.db.session import engine, get_db
logger.debug("--- main.py - Imported engine, get_db from app.db.session ---")
from app.db import base_class
logger.debug("--- main.py - Imported base_class from app.db ---")
from app.core.config import settings
logger.debug(f"--- main.py - Imported settings. Project Name: {settings.PROJECT_NAME} ---")
from app.crud.crud_room import seed_initial_world
logger.debug("--- main.py - Imported seed_initial_world ---")
from app.crud.crud_item import seed_initial_items 
logger.debug("--- main.py - Imported seed_initial_items ---")
from app.crud.crud_mob import seed_initial_mob_templates
logger.debug("--- main.py - Imported seed_initial_mob_templates ---")
from app.game_logic.combat import start_combat_ticker_task, stop_combat_ticker_task
logger.debug("--- main.py - Imported combat_manager tasks ---")
from app.crud.crud_character_class import seed_initial_character_class_templates 
logger.debug("--- main.py - Imported seed_initial_character_class_templates ---")
from app.crud.crud_skill import seed_initial_skill_templates 
logger.debug("--- main.py - Imported seed_initial_skill_templates ---")
from app.crud.crud_trait import seed_initial_trait_templates 
logger.debug("--- main.py - Imported seed_initial_trait_templates ---")
from app.game_logic.world_ticker import start_world_ticker_task, stop_world_ticker_task
logger.debug("--- main.py - Imported world_ticker tasks ---")
from app.crud.crud_mob_spawn_definition import seed_initial_mob_spawn_definitions 
logger.debug("--- main.py - Imported seed_initial_mob_spawn_definitions ---")
from app.crud.crud_npc import seed_initial_npc_templates
logger.debug("--- main.py - Imported seed_initial_npc_templates ---")
from app.game_logic.npc_dialogue_ticker import start_dialogue_ticker_task, stop_dialogue_ticker_task
logger.debug("--- main.py - Imported npc_dialogue_ticker shit ---")
logger.debug("--- main.py - About to call Base.metadata.create_all(bind=engine) ---")
try:
    base_class.Base.metadata.create_all(bind=engine)
    logger.info("--- main.py - Base.metadata.create_all(bind=engine) COMPLETED ---")
except Exception as e:
    logger.error(f"--- main.py - ERROR during Base.metadata.create_all: {e} ---", exc_info=True)
    # Depending on the severity, you might want to sys.exit() here

logger.debug("--- main.py - Creating FastAPI app instance ---")
app = FastAPI(title=settings.PROJECT_NAME)
logger.info("--- main.py - FastAPI app instance CREATED ---")

origins = [
    "http://localhost:5174",
    "http://192.168.88.115:5174",
    "https://llmud.trazen.org"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup_sync():
    logger.info("--- main.py - START of on_startup_sync event ---")
    db: Session = next(get_db())
    logger.debug("--- main.py - on_startup_sync: Acquired DB session ---")
    try:
        logger.info("--- main.py - on_startup_sync: Running startup event: Seeding initial data... ---")
        
        # CORRECT ORDER:
        # 1. Seed items FIRST
        seed_initial_items(db)
        logger.debug("--- main.py - on_startup_sync: seed_initial_items COMPLETED ---")

        # 2. THEN seed the world (rooms/exits), which might place items
        seed_initial_world(db)        
        logger.debug("--- main.py - on_startup_sync: seed_initial_world COMPLETED ---")
        
        # 3. THEN other things
        seed_initial_mob_templates(db)        
        logger.debug("--- main.py - on_startup_sync: seed_initial_mob_templates COMPLETED ---")

        seed_initial_npc_templates(db) # <<< ADD THIS LINE
        logger.debug("--- main.py - on_startup_sync: seed_initial_npc_templates COMPLETED ---")
        
        seed_initial_character_class_templates(db)
        logger.debug("--- main.py - on_startup_sync: seed_initial_character_class_templates COMPLETED ---")
        
        seed_initial_skill_templates(db)
        logger.debug("--- main.py - on_startup_sync: seed_initial_skill_templates COMPLETED ---")
        
        seed_initial_trait_templates(db)
        logger.debug("--- main.py - on_startup_sync: seed_initial_trait_templates COMPLETED ---")
        
        seed_initial_mob_spawn_definitions(db)
        logger.debug("--- main.py - on_startup_sync: seed_initial_mob_spawn_definitions COMPLETED ---")
        
        logger.info("--- main.py - on_startup_sync: Starting combat ticker... ---")
        start_combat_ticker_task()
        logger.debug("--- main.py - on_startup_sync: Combat ticker STARTED ---")      

        logger.info("--- main.py - on_startup_sync: Starting NPC dialogue ticker... ---")
        start_dialogue_ticker_task()        
        logger.info("--- main.py - on_startup_sync: Startup event processing FINISHED ---")

        logger.info("--- main.py - on_startup_sync: Starting world ticker... ---") 
        start_world_ticker_task()    
        logger.debug("--- main.py - on_startup_sync: World ticker STARTED ---")     
        logger.info("--- main.py - on_startup_sync: Startup event processing FINISHED ---")
    except Exception as e_startup:
        logger.error(f"--- main.py - ERROR during on_startup_sync: {e_startup} ---", exc_info=True)
    finally:
        logger.debug("--- main.py - on_startup_sync: Closing DB session ---")
        db.close()
        logger.debug("--- main.py - on_startup_sync: DB session CLOSED ---")
    logger.info("--- main.py - END of on_startup_sync event ---")

logger.debug("--- main.py - About to include v1_api_router ---")
app.include_router(v1_api_router, prefix=settings.API_V1_STR)
logger.debug("--- main.py - v1_api_router INCLUDED ---")

logger.debug("--- main.py - About to include ws_router ---")
app.include_router(ws_router)
logger.debug("--- main.py - ws_router INCLUDED ---")

@app.get("/")
async def root():
    logger.debug("--- main.py - GET / request received ---")
    return {"message": f"Welcome to {settings.PROJECT_NAME}. Now with a World Ticker humming in the background!"}

logger.info("--- main.py - FastAPI app instance configured. End of file. ---")