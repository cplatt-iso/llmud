# backend/app/main.py
import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import sys # For detailed print statements

print(f"--- DEBUG: main.py - Top of file, Python version: {sys.version} ---", flush=True)

from app.api.v1.api_router import api_router as v1_api_router
print("--- DEBUG: main.py - Imported v1_api_router ---", flush=True)
from app.websocket_router import router as ws_router
print("--- DEBUG: main.py - Imported ws_router ---", flush=True)
from app.db.session import engine, get_db
print("--- DEBUG: main.py - Imported engine, get_db from app.db.session ---", flush=True)
from app.db import base_class
print("--- DEBUG: main.py - Imported base_class from app.db ---", flush=True)
from app.core.config import settings
print(f"--- DEBUG: main.py - Imported settings. Project Name: {settings.PROJECT_NAME} ---", flush=True)
from app.crud.crud_room import seed_initial_world
print("--- DEBUG: main.py - Imported seed_initial_world ---", flush=True)
from app.crud.crud_item import seed_initial_items 
print("--- DEBUG: main.py - Imported seed_initial_items ---", flush=True)
from app.crud.crud_mob import seed_initial_mob_templates
print("--- DEBUG: main.py - Imported seed_initial_mob_templates ---", flush=True)
from app.game_logic.combat_manager import start_combat_ticker_task, stop_combat_ticker_task
print("--- DEBUG: main.py - Imported combat_manager tasks ---", flush=True)
from app.crud.crud_character_class import seed_initial_character_class_templates 
print("--- DEBUG: main.py - Imported seed_initial_character_class_templates ---", flush=True)
from app.crud.crud_skill import seed_initial_skill_templates 
print("--- DEBUG: main.py - Imported seed_initial_skill_templates ---", flush=True)
from app.crud.crud_trait import seed_initial_trait_templates 
print("--- DEBUG: main.py - Imported seed_initial_trait_templates ---", flush=True)
from app.game_logic.world_ticker import start_world_ticker_task, stop_world_ticker_task
print("--- DEBUG: main.py - Imported world_ticker tasks ---", flush=True)
from app.crud.crud_mob_spawn_definition import seed_initial_mob_spawn_definitions 
print("--- DEBUG: main.py - Imported seed_initial_mob_spawn_definitions ---", flush=True)

print("--- DEBUG: main.py - About to call Base.metadata.create_all(bind=engine) ---", flush=True)
try:
    base_class.Base.metadata.create_all(bind=engine)
    print("--- DEBUG: main.py - Base.metadata.create_all(bind=engine) COMPLETED ---", flush=True)
except Exception as e:
    print(f"--- DEBUG: main.py - ERROR during Base.metadata.create_all: {e} ---", flush=True)
    # Depending on the severity, you might want to sys.exit() here

print("--- DEBUG: main.py - Creating FastAPI app instance ---", flush=True)
app = FastAPI(title=settings.PROJECT_NAME)
print("--- DEBUG: main.py - FastAPI app instance CREATED ---", flush=True)

@app.on_event("startup")
def on_startup_sync(): # Renamed to avoid clash if we make it async later
    print("--- DEBUG: main.py - START of on_startup_sync event ---", flush=True)
    db: Session = next(get_db())
    print("--- DEBUG: main.py - on_startup_sync: Acquired DB session ---", flush=True)
    try:
        print("--- DEBUG: main.py - on_startup_sync: Running startup event: Seeding initial world... ---", flush=True)
        seed_initial_world(db)        
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_world COMPLETED ---", flush=True)
        seed_initial_mob_templates(db)        
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_mob_templates COMPLETED ---", flush=True)
        seed_initial_items(db)
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_items COMPLETED ---", flush=True)
        seed_initial_character_class_templates(db)
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_character_class_templates COMPLETED ---", flush=True)
        seed_initial_skill_templates(db)
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_skill_templates COMPLETED ---", flush=True)
        seed_initial_trait_templates(db) # Make sure this is imported if you uncomment it
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_trait_templates COMPLETED ---", flush=True)
        seed_initial_mob_spawn_definitions(db)
        print("--- DEBUG: main.py - on_startup_sync: seed_initial_mob_spawn_definitions COMPLETED ---", flush=True)
        
        print("--- DEBUG: main.py - on_startup_sync: Starting combat ticker... ---", flush=True)
        start_combat_ticker_task()
        print("--- DEBUG: main.py - on_startup_sync: Combat ticker STARTED ---", flush=True)      

        print("--- DEBUG: main.py - on_startup_sync: Starting world ticker... ---", flush=True) 
        start_world_ticker_task()    
        print("--- DEBUG: main.py - on_startup_sync: World ticker STARTED ---", flush=True)     
        print("--- DEBUG: main.py - on_startup_sync: Startup event processing FINISHED ---", flush=True)
    except Exception as e_startup:
        print(f"--- DEBUG: main.py - ERROR during on_startup_sync: {e_startup} ---", flush=True)
    finally:
        print("--- DEBUG: main.py - on_startup_sync: Closing DB session ---", flush=True)
        db.close()
        print("--- DEBUG: main.py - on_startup_sync: DB session CLOSED ---", flush=True)
    print("--- DEBUG: main.py - END of on_startup_sync event ---", flush=True)

print("--- DEBUG: main.py - About to include v1_api_router ---", flush=True)
app.include_router(v1_api_router, prefix=settings.API_V1_STR)
print("--- DEBUG: main.py - v1_api_router INCLUDED ---", flush=True)

print("--- DEBUG: main.py - About to include ws_router ---", flush=True)
app.include_router(ws_router)
print("--- DEBUG: main.py - ws_router INCLUDED ---", flush=True)

@app.get("/")
async def root():
    print("--- DEBUG: main.py - GET / request received ---")
    return {"message": f"Welcome to {settings.PROJECT_NAME}. Now with a World Ticker humming in the background!"}

print("--- DEBUG: main.py - FastAPI app instance configured. End of file. ---", flush=True)