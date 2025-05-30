# backend/app/main.py
import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.api.v1.api_router import api_router as v1_api_router
from app.websocket_router import router as ws_router # <<< NEW
from app.db.session import engine, get_db
from app.db import base_class
from app.core.config import settings
from app.crud.crud_room import seed_initial_world
from app.crud.crud_item import seed_initial_items 
from app.crud.crud_mob import seed_initial_mob_templates, seed_initial_mob_spawns
from app.game_logic.combat_manager import start_combat_ticker_task # <<< NEW

base_class.Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.PROJECT_NAME)

@app.on_event("startup")
def on_startup_sync(): # Renamed to avoid clash if we make it async later
    db: Session = next(get_db())
    try:
        print("Running startup event: Seeding initial world...")
        seed_initial_world(db)
        # ... other seeders ...
        seed_initial_mob_templates(db)
        seed_initial_mob_spawns(db)
        
        print("Starting combat ticker...")
        start_combat_ticker_task() # Call the function to create the task
        print("Startup event finished.")        
    finally:
        db.close()

app.include_router(v1_api_router, prefix=settings.API_V1_STR)
app.include_router(ws_router) # <<< ADDED WEBSOCKET ROUTER (usually no prefix or /ws)

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}. Now with WebSockets for combat!"}

print("FastAPI app instance created.")