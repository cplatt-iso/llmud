from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
import uuid
# from pydantic import BaseModel # No longer needed here if CommandRequest is in schemas
from typing import Optional # Dict not needed for payload type

from .... import schemas # schemas.CommandRequest, schemas.CommandResponse
from ....db.session import get_db
from ....crud import crud_room, crud_character
from ....api.dependencies import get_current_active_character # <<< CHANGED
from .... import models

router = APIRouter()

# class CommandRequestWithCharacter(BaseModel): # <<< REMOVED
#     command: str
#     character_id: uuid.UUID

@router.post("", response_model=schemas.CommandResponse) # <<< CHANGED response_model
async def process_command_for_character(
    payload: schemas.CommandRequest = Body(...), # <<< CHANGED payload type
    db: Session = Depends(get_db),
    acting_character_orm: models.Character = Depends(get_current_active_character) # <<< CHANGED dependency
):
    command_text = payload.command.lower().strip()
    message_to_player: Optional[str] = None

    # Character validation and ownership is now handled by get_current_active_character.
    
    current_room_orm = crud_room.get_room_by_id(db, room_id=acting_character_orm.current_room_id)
    
    if current_room_orm is None:
        print(f"CRITICAL DATA ERROR: Character '{acting_character_orm.name}' (ID: {acting_character_orm.id}) "
              f"has current_room_id '{acting_character_orm.current_room_id}' which was not found in rooms table.")
        return schemas.CommandResponse( # <<< CHANGED response
            room_data=None, 
            message_to_player=f"Character '{acting_character_orm.name}' is in an invalid room. Please contact an administrator."
        )

    # --- Process "look" command ---
    if command_text == "look" or command_text.startswith("look "): # Basic look
        # message_to_player = "You look around." # Optional message
        # The room_data itself will provide the description.
        return schemas.CommandResponse(
            room_data=schemas.RoomInDB.from_orm(current_room_orm),
            message_to_player=message_to_player # Can be None
        )

    # --- Process Movement Command ---
    moved = False
    target_room_orm: Optional[models.Room] = None 
    
    current_exits = current_room_orm.exits if current_room_orm.exits is not None else {}
    possible_directions = ["north", "south", "east", "west", "up", "down"]
    cleaned_command = command_text.split(" ")[-1] 
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    target_direction = direction_map.get(cleaned_command, cleaned_command)

    is_movement_attempt = target_direction in possible_directions

    if is_movement_attempt:
        if target_direction in current_exits:
            next_room_uuid_str = current_exits.get(target_direction)
            if next_room_uuid_str:
                try:
                    target_room_uuid = uuid.UUID(hex=next_room_uuid_str)
                    potential_target_room_orm = crud_room.get_room_by_id(db, room_id=target_room_uuid)
                    if potential_target_room_orm:
                        target_room_orm = potential_target_room_orm
                        moved = True
                    else:
                        message_to_player = "The path ahead seems to vanish into thin air."
                        print(f"ERROR: Target room UUID '{target_room_uuid}' (for direction '{target_direction}') not found from room '{current_room_orm.name}'.")
                except ValueError:
                    message_to_player = "The exit in that direction appears to be corrupted."
                    print(f"ERROR: Invalid UUID string '{next_room_uuid_str}' in exit data for room '{current_room_orm.name}'.")
            else: # Should not happen if key exists (e.g. "north": null)
                message_to_player = "The way in that direction is unclear."
                print(f"Exit '{target_direction}' exists but has no target UUID in room '{current_room_orm.name}'.")
        else: # It was a movement attempt (e.g., "north") but no such exit
            message_to_player = "You can't go that way."
    else: # Not "look" and not a recognized movement keyword/direction
        message_to_player = f"I don't understand the command: '{command_text}'."


    if moved and target_room_orm:
        updated_character_orm = crud_character.update_character_room(
            db, 
            character_id=acting_character_orm.id, 
            new_room_id=target_room_orm.id  
        )
        if updated_character_orm:
            print(f"Character '{updated_character_orm.name}' moved to '{target_room_orm.name}'.")
            # For successful move, message_to_player can be None; new room data implies success.
            # Or, could set: message_to_player = f"You move {target_direction}."
            return schemas.CommandResponse(
                room_data=schemas.RoomInDB.from_orm(target_room_orm),
                message_to_player=None 
            )
        else:
            # This is a server-side error during update.
            print(f"ERROR: Failed to update character room for char_id '{acting_character_orm.id}'.")
            message_to_player = "You try to move, but an unseen force holds you in place."
            # Fall through to return current room with this message
    
    # If no move happened (moved is False), or a move attempt failed validation, or DB update failed.
    # message_to_player should be set if it wasn't a successful move.
    return schemas.CommandResponse(
        room_data=schemas.RoomInDB.from_orm(current_room_orm),
        message_to_player=message_to_player
    )