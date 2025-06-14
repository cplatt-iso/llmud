# backend/app/services/room_service.py
import logging
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app import crud, models, schemas
from app import websocket_manager # MODIFIED IMPORT

logger = logging.getLogger(__name__)

def get_room_details(db: Session, *, x: int, y: int, z: int) -> Optional[schemas.RoomInDB]:
    """
    Service layer to get room details.
    Fetches ORM model from CRUD and converts to Pydantic schema.
    """
    room_orm_model = crud.crud_room.get_room_by_coords(db=db, x=x, y=y, z=z)
    if room_orm_model:
        # Convert the SQLAlchemy ORM model instance to a Pydantic schema instance
        # Pydantic v2 uses .from_orm() via the Config.from_attributes = True setting
        return schemas.RoomInDB.from_orm(room_orm_model)
    return None

def get_player_ids_in_room(db: Session, room_id: uuid.UUID, exclude_player_ids: Optional[List[uuid.UUID]] = None) -> List[uuid.UUID]:
    # This function now correctly uses the connection_manager's cache
    # and doesn't need a direct DB query for this specific info if cache is reliable.
    # However, for robustly getting players in a room, especially if cache could be stale
    # or for operations needing DB consistency, a DB query might be preferred.
    # The current ConnectionManager.broadcast_to_room handles this logic internally.
    # This helper might be for other uses.

    # Assuming connection_manager holds the authoritative list of online players and their locations
    player_ids_in_target_room = []
    # Access connection_manager via the imported module
    for player_id, char_id in websocket_manager.connection_manager.player_active_characters.items():
        if websocket_manager.connection_manager.character_locations.get(char_id) == room_id:
            if not exclude_player_ids or player_id not in exclude_player_ids:
                player_ids_in_target_room.append(player_id)
    return player_ids_in_target_room

async def broadcast_room_update(room_id: uuid.UUID, updated_room_data: schemas.RoomInDB, exclude_player_ids: Optional[List[uuid.UUID]] = None):
    payload = {
        "type": "room_update",
        "room_data": updated_room_data.model_dump(exclude_none=True)
    }
    # Access connection_manager via the imported module
    await websocket_manager.connection_manager.broadcast_to_room(payload, room_id, exclude_player_ids=exclude_player_ids)