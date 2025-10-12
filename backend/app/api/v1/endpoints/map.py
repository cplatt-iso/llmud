# backend/app/api/v1/endpoints/map.py
import uuid  # Ensure uuid is imported
from typing import Any, Dict  # Added Dict

from app import crud, models, schemas
from app.api.dependencies import get_current_active_character
from app.db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# from app.schemas.common_structures import ExitDetail # Not directly needed here anymore with simplified exits

router = APIRouter()


@router.get("/level_data", response_model=schemas.MapLevelDataResponse)
def get_map_data_for_current_level(
    *,
    db: Session = Depends(get_db),
    active_character: models.Character = Depends(get_current_active_character)
) -> Any:
    if active_character.current_room_id is None:
        raise HTTPException(
            status_code=404, detail="Active character is not in a valid room."
        )

    current_room = crud.crud_room.get_room_by_id(
        db, room_id=active_character.current_room_id
    )
    if not current_room:
        raise HTTPException(
            status_code=500, detail="Current room for active character not found."
        )

    character_z_level = current_room.z
    rooms_on_level_orm = crud.crud_room.get_rooms_by_z_level(
        db, z_level=character_z_level
    )

    map_rooms_data: list[schemas.MapRoomData] = []
    for room_orm in rooms_on_level_orm:
        # Process exits for MapRoomData: extract only target_room_id as a string
        simple_exits_for_map: Dict[str, str] = {}
        if room_orm.exits:
            for direction, exit_detail_dict in room_orm.exits.items():
                if (
                    isinstance(exit_detail_dict, dict)
                    and "target_room_id" in exit_detail_dict
                ):
                    # Ensure target_room_id is a string for the MapRoomData schema
                    simple_exits_for_map[direction] = str(
                        exit_detail_dict["target_room_id"]
                    )
                # else: Malformed exit data in DB, maybe log a warning

        map_rooms_data.append(
            schemas.MapRoomData(
                id=room_orm.id,
                x=room_orm.x,
                y=room_orm.y,
                name=room_orm.name,
                exits=simple_exits_for_map,  # Pass the simplified exits dict
                is_current_room=(room_orm.id == active_character.current_room_id),
                is_visited=True,
                room_type=room_orm.room_type,
            )
        )

    return schemas.MapLevelDataResponse(
        z_level=character_z_level,
        current_room_id=active_character.current_room_id,
        rooms=map_rooms_data,
        current_zone_name=current_room.zone_name,
        current_zone_level_range=current_room.zone_level_range,
    )
