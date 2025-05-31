# backend/app/api/v1/endpoints/map.py (NEW FILE)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any # List for type hint

from app import schemas, models, crud
from app.db.session import get_db
from app.api.dependencies import get_current_active_character

router = APIRouter()

@router.get("/level_data", response_model=schemas.MapLevelDataResponse)
def get_map_data_for_current_level(
    *,
    db: Session = Depends(get_db),
    active_character: models.Character = Depends(get_current_active_character)
) -> Any:
    """
    Provides map data for the Z-level the active character is currently on.
    """
    if active_character.current_room_id is None:
        # This should ideally not happen if a character is active
        raise HTTPException(status_code=404, detail="Active character is not in a valid room.")

    # Fetch the current room to get the Z-level
    # current_room_orm = crud.crud_room.get_room_by_id(db, room_id=active_character.current_room_id)
    # We can get Z directly from the character's current_room object if it's loaded with coords,
    # or from the current_room_orm if we fetch it.
    # For simplicity, let's assume active_character.current_room (if relationship is loaded) has x,y,z
    # Or, safer, fetch the current room again to ensure we have its Z.
    # Let's rely on the character's current room being valid and its details accessible
    # For this, we need to ensure current_room is loaded on active_character, or we fetch it.
    # The get_current_active_character dependency already fetches the character.
    # We need to ensure its `current_room_id` can be used to get the room's Z.

    current_room = crud.crud_room.get_room_by_id(db, room_id=active_character.current_room_id)
    if not current_room:
         raise HTTPException(status_code=500, detail="Current room for active character not found.")
    
    character_z_level = current_room.z

    rooms_on_level_orm = crud.crud_room.get_rooms_by_z_level(db, z_level=character_z_level)

    map_rooms_data: list[schemas.MapRoomData] = []
    for room_orm in rooms_on_level_orm:
        map_rooms_data.append(
            schemas.MapRoomData(
                id=room_orm.id,
                x=room_orm.x,
                y=room_orm.y,
                name=room_orm.name,
                exits=room_orm.exits or {}, # Ensure exits is a dict, not None
                is_current_room=(room_orm.id == active_character.current_room_id),
                is_visited=True # Placeholder: For now, all rooms on the Z-level are "visited"
            )
        )
    
    return schemas.MapLevelDataResponse(
        z_level=character_z_level,
        current_room_id=active_character.current_room_id,
        rooms=map_rooms_data
    )