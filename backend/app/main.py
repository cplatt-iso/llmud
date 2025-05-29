# backend/app/main.py
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from .api.v1.api_router import api_router as v1_api_router
from .db.session import engine, get_db # Import engine and get_db
from .db import base_class # To access Base for create_all
from .crud import crud_room # For init_first_room_if_not_exists
from .core.config import settings # Import settings for project name, etc.
from .crud.crud_room import seed_initial_world

# This line creates tables if they don't exist.
# IMPORTANT: In a production app, you'd use Alembic migrations for schema management,
# not create_all(). This is okay for initial development.
# Comment this out once Alembic is fully managing your schema.
base_class.Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

fake_player_state = {
    "current_room_coords": {"x": 0, "y": 0, "z": 0} # Start in the Genesis room
}

@app.on_event("startup")
def on_startup():
    db: Session = next(get_db())
    try:
        print("Running startup event: Seeding initial world with UUIDs...")
        seed_initial_world(db) # Call the new seeding function
        print("Startup event finished.")
    finally:
        db.close()

app.include_router(v1_api_router, prefix=settings.API_V1_STR) # Using API_V1_STR from settings

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}. It's now SQL-powered, allegedly."}

print("FastAPI app instance created. Database tables (should be) created by create_all().")
print(f"Database URL being used by SQLAlchemy engine: {engine.url}")