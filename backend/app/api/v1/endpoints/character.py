# backend/app/api/v1/endpoints/character.py
from fastapi import APIRouter, Depends, HTTPException, status, Body # Added Body
from sqlalchemy.orm import Session
import uuid
from typing import Any, List

from .... import schemas, crud, models # Import models for type hint
from ....db.session import get_db
from ....crud.crud_room import get_room_by_coords # To find the starting room
from ....api.dependencies import get_current_player # <<< IMPORT AUTH DEPENDENCY

router = APIRouter()

# CharacterCreateRequest no longer needs player_id from client
# We'll use schemas.CharacterCreate directly as the payload,
# which contains 'name' and 'class_name'.
# class CharacterCreateRequest(schemas.CharacterCreate):
#     player_id: uuid.UUID # REMOVE THIS

@router.post("/create", response_model=schemas.Character, status_code=status.HTTP_201_CREATED)
def create_new_character_for_current_player( # Renamed for clarity
    *,
    db: Session = Depends(get_db),
    character_payload: schemas.CharacterCreate = Body(...), # Payload is now just name/class
    current_player: models.Player = Depends(get_current_player) # <<< GET AUTHENTICATED PLAYER
) -> Any:
    """
    Create a new character for the currently authenticated player.
    Places the character in the starting room (0,0,0).
    """
    # 1. Player ID is now current_player.id from the token. No need to validate it separately.
    
    # 2. Check if character name is already taken (globally for now, or per player later)
    existing_character = crud.crud_character.get_character_by_name(db, name=character_payload.name)
    if existing_character:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A character with the name '{character_payload.name}' already exists."
        )
    
    # 3. Find the starting room (e.g., Genesis Room at 0,0,0)
    start_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0)
    if not start_room_orm:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Starting room not found. Cannot create character. Server misconfiguration."
        )
    
    # 4. Create the character, passing current_player.id
    character = crud.crud_character.create_character(
        db, 
        character_in=character_payload, # This is schemas.CharacterCreate instance
        player_id=current_player.id,    # Use ID from authenticated player
        initial_room_id=start_room_orm.id
    )
    
    print(f"Character '{character.name}' created for player '{current_player.username}', starting in room '{start_room_orm.name}'.")
    return character

# Endpoint to get characters for the CURRENTLY AUTHENTICATED player
@router.get("/mine", response_model=List[schemas.Character]) # Changed path, uses auth
def read_characters_for_current_player( # Renamed for clarity
    db: Session = Depends(get_db),
    current_player: models.Player = Depends(get_current_player) # <<< GET AUTHENTICATED PLAYER
):
    """
    Retrieve all characters for the currently authenticated player.
    """
    characters = crud.crud_character.get_characters_by_player(db, player_id=current_player.id)
    return characters

# Keep the old /by_player/{player_id} if you want an admin-like endpoint,
# but ensure it has proper authorization (e.g., only for superusers).
# For now, let's assume we replace it with "/mine". If you need both, ensure distinct logic.
# For example, to remove or comment out the old one:
# # @router.get("/by_player/{player_id}", response_model=List[schemas.Character])
# # def read_characters_for_player( ... old implementation ... ): ...