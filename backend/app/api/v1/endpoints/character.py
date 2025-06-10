# backend/app/api/v1/endpoints/character.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from sqlalchemy.orm import Session
import uuid
from typing import Any, List

from .... import schemas, crud, models
from ....db.session import get_db
# from ....crud.crud_room import get_room_by_coords # No longer needed for this file directly if only used in create
from ....api.dependencies import get_current_player, get_current_active_character
from ....game_state import active_game_sessions # <<< ADDED THIS IMPORT
from app.schemas.abilities import CharacterAbilitiesResponse

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/create", response_model=schemas.Character, status_code=status.HTTP_201_CREATED)
def create_new_character_for_current_player(
    *,
    db: Session = Depends(get_db),
    character_payload: schemas.CharacterCreate = Body(...), # Contains name, optional class_name
    current_player: models.Player = Depends(get_current_player)
) -> Any:
    # ... (existing_character check remains the same) ...
    existing_character = crud.crud_character.get_character_by_name(db, name=character_payload.name)
    if existing_character:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A character with the name '{character_payload.name}' already exists."
        )
    
    start_room_orm = crud.crud_room.get_room_by_coords(db, x=0, y=0, z=0)
    if not start_room_orm:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Starting room not found. Cannot create character. Server misconfiguration."
        )
    
    # The character_payload (schemas.CharacterCreate) now passes name and class_name (optional)
    # to crud.crud_character.create_character.
    # The CRUD function handles looking up the class template and applying defaults/modifiers.
    character = crud.crud_character.create_character(
        db,
        character_in=character_payload, # Contains name and potentially class_name
        player_id=current_player.id,
        initial_room_id=start_room_orm.id
    )
    
    print(f"Character '{character.name}' (Class: {character.class_name}) created for player '{current_player.username}', starting in room '{start_room_orm.name}'.")
    return character # FastAPI will convert to schemas.Character


@router.get("/mine", response_model=List[schemas.Character])
def read_characters_for_current_player(
    db: Session = Depends(get_db),
    current_player: models.Player = Depends(get_current_player)
):
    """
    Retrieve all characters for the currently authenticated player.
    """ 
    characters = crud.crud_character.get_characters_by_player(db, player_id=current_player.id)
    return characters


@router.post("/{character_id}/select", response_model=schemas.RoomInDB) # <<< NEW ENDPOINT
def select_character_for_session(
    *,
    db: Session = Depends(get_db),
    character_id: uuid.UUID,
    current_player: models.Player = Depends(get_current_player)
) -> Any:
    """
    Selects a character to be the active character for the player's session.
    Returns the character's current room data.
    """
    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character with ID {character_id} not found."
        )
    
    if character.player_id != current_player.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation not permitted: This character does not belong to you."
        )

    # Set this character as active for the player's session
    active_game_sessions[current_player.id] = character.id
    
    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=character.current_room_id)
    if not current_room_orm:
        active_game_sessions.pop(current_player.id, None) # Clean up inconsistent state
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Character '{character.name}' (ID: {character.id}) is in an invalid room (ID: {character.current_room_id}). Data integrity error. Session not started."
        )
    
    print(f"Player '{current_player.username}' (ID: {current_player.id}) selected character '{character.name}' (ID: {character.id}).")
    print(f"Active sessions: {active_game_sessions}") # For debugging
    return current_room_orm # FastAPI will convert ORM to schemas.RoomInDB

@router.get("/me/active", response_model=schemas.Character)
def get_current_active_character_details(
    *,
    # This glorious dependency does all the work for us.
    active_character: models.Character = Depends(get_current_active_character)
) -> Any:
    """
    Retrieve the full details for the currently selected character in the session.
    """
    return active_character

@router.get("/me/inventory", response_model=schemas.CharacterInventoryDisplay)
def get_character_inventory_display(
    *,
    db: Session = Depends(get_db),
    active_character: models.Character = Depends(get_current_active_character)
) -> Any:
    """
    Retrieve and organize the active character's inventory for display.
    """
    inventory_items_orm = crud.crud_character_inventory.get_character_inventory(db, character_id=active_character.id)
    
    equipped_items = {}
    backpack_items = []
    
    for item_orm in inventory_items_orm:
        item_schema = schemas.CharacterInventoryItem.from_orm(item_orm)
        if item_schema.equipped and item_schema.equipped_slot:
            equipped_items[item_schema.equipped_slot] = item_schema
        else:
            backpack_items.append(item_schema)
            
    return schemas.CharacterInventoryDisplay(
        equipped_items=equipped_items,
        backpack_items=backpack_items,
        platinum=active_character.platinum_coins,
        gold=active_character.gold_coins,
        silver=active_character.silver_coins,
        copper=active_character.copper_coins
    )

@router.get("/me/abilities", response_model=CharacterAbilitiesResponse)
async def get_player_abilities(
    *,
    db: Session = Depends(get_db),
    current_char: models.Character = Depends(get_current_active_character),
):
    """
    Retrieve all available skills and traits for the player's character class.
    """
    abilities_data = crud.crud_character.get_character_abilities(db, character=current_char)
    return CharacterAbilitiesResponse(**abilities_data)