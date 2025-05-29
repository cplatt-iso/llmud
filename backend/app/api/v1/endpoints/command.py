from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
import uuid
from pydantic import BaseModel
from typing import Optional, Dict # Import Dict

from .... import schemas
from ....db.session import get_db
from ....crud import crud_room, crud_character
from ....api.dependencies import get_current_player
from .... import models

router = APIRouter()

class CommandRequestWithCharacter(BaseModel):
    command: str
    character_id: uuid.UUID

@router.post("", response_model=schemas.RoomInDB)
async def process_command_for_character(
    payload: CommandRequestWithCharacter = Body(...),
    db: Session = Depends(get_db),
    current_player: models.Player = Depends(get_current_player)
):
    command_text = payload.command.lower().strip()
    
    # --- 1. Validate Character and Ownership ---
    acting_character_orm = crud_character.get_character(db, character_id=payload.character_id)
    
    if acting_character_orm is None: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Character with ID {payload.character_id} not found."
        )

    # Assuming models.Player.id is Mapped[uuid.UUID] and models.Character.player_id is Mapped[uuid.UUID]
    # Pylance should understand these are UUIDs when accessed.
    if acting_character_orm.player_id != current_player.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted: This character does not belong to you."
        )

    # --- 2. Get Character's Current Room ---
    # Assuming models.Character.current_room_id is Mapped[uuid.UUID]
    current_room_orm = crud_room.get_room_by_id(db, room_id=acting_character_orm.current_room_id)
    
    if current_room_orm is None:
        print(f"CRITICAL DATA ERROR: Character '{acting_character_orm.name}' (ID: {acting_character_orm.id}) "
              f"has current_room_id '{acting_character_orm.current_room_id}' which was not found in rooms table.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(f"Character '{acting_character_orm.name}' is in an invalid room. ")
        )

    # --- 3. Process Movement Command ---
    moved = False
    next_room_uuid_str: Optional[str] = None 
    target_room_uuid: Optional[uuid.UUID] = None 

    current_exits: Dict[str, str] = current_room_orm.exits if current_room_orm.exits is not None else {}

    # Simplified exit checking logic
    possible_directions = ["north", "south", "east", "west", "up", "down"]
    cleaned_command = command_text.split(" ")[-1] # Takes "go north" -> "north", or "n" -> "n"

    # Map short commands to full direction names if necessary, or ensure your exits dict uses short names
    direction_map = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
    target_direction = direction_map.get(cleaned_command, cleaned_command) # Convert "n" to "north" etc.

    if target_direction in current_exits:
        next_room_uuid_str = current_exits.get(target_direction)
        if next_room_uuid_str: # Ensure a value was actually retrieved
            moved = True
        else:
            print(f"Exit '{target_direction}' found but has no target UUID in room '{current_room_orm.name}'.")
    else:
        print(f"Command '{command_text}' (parsed as direction '{target_direction}') for char '{acting_character_orm.name}' is not a valid exit from room '{current_room_orm.name}'.")


    if moved and next_room_uuid_str:
        try:
            target_room_uuid = uuid.UUID(hex=next_room_uuid_str)
        except ValueError:
            print(f"ERROR: Invalid UUID string '{next_room_uuid_str}' in exit data for room '{current_room_orm.name}'.")
            moved = False 
        
        if moved and target_room_uuid: 
            target_room_orm = crud_room.get_room_by_id(db, room_id=target_room_uuid)
            if target_room_orm:
                # Pylance should understand .id on ORM instances (if Mapped) returns the scalar type
                updated_character_orm = crud_character.update_character_room(
                    db, 
                    character_id=acting_character_orm.id, 
                    new_room_id=target_room_orm.id  
                )
                if updated_character_orm:
                    print(f"Character '{updated_character_orm.name}' moved to '{target_room_orm.name}'.")
                    return schemas.RoomInDB.from_orm(target_room_orm)
                else:
                    print(f"ERROR: Failed to update character room for char_id '{acting_character_orm.id}'.")
            else:
                print(f"ERROR: Target room UUID '{target_room_uuid}' not found.")
    
    return schemas.RoomInDB.from_orm(current_room_orm)