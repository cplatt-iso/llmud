# backend/app/api/v1/endpoints/inventory.py
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
import uuid
from typing import List

from .... import schemas, models, crud
from ....db.session import get_db
from ....api.dependencies import get_current_active_character
from ....models.item import EQUIPMENT_SLOTS # For constructing display

router = APIRouter()

def format_inventory_for_display(
    inventory_items: List[models.CharacterInventoryItem]
) -> schemas.CharacterInventoryDisplay:
    """Helper function to format raw inventory items into the display schema."""
    equipped_dict: dict[str, schemas.CharacterInventoryItem] = {}
    backpack_list: list[schemas.CharacterInventoryItem] = []

    for inv_item_orm in inventory_items:
        # Convert ORM to Pydantic schema. The item sub-object should also be converted.
        # schemas.CharacterInventoryItem.from_orm(inv_item_orm) should handle this due to nested Config.
        item_schema = schemas.CharacterInventoryItem.from_orm(inv_item_orm)
        if inv_item_orm.equipped and inv_item_orm.equipped_slot:
            equipped_dict[inv_item_orm.equipped_slot] = item_schema
        else:
            backpack_list.append(item_schema)
            
    return schemas.CharacterInventoryDisplay(equipped_items=equipped_dict, backpack_items=backpack_list)


@router.get("/mine", response_model=schemas.CharacterInventoryDisplay)
def get_my_inventory(
    db: Session = Depends(get_db),
    current_character: models.Character = Depends(get_current_active_character),
):
    """
    Retrieve the inventory for the currently active character.
    """
    inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        db, character_id=current_character.id
    )
    return format_inventory_for_display(inventory_items_orm)


@router.post("/equip/{inventory_item_id}", response_model=schemas.CommandResponse) # Using CommandResponse for feedback
def equip_inventory_item_api(
    inventory_item_id: uuid.UUID,
    payload: schemas.EquipRequest = Body(None), # Payload can be optional if target_slot isn't always needed
    db: Session = Depends(get_db),
    current_character: models.Character = Depends(get_current_active_character),
):
    """
    Equip an item from the character's inventory.
    inventory_item_id is the UUID of the CharacterInventoryItem entry.
    """
    target_slot_from_payload = payload.target_slot if payload else None
    
    updated_inv_item, message = crud.crud_character_inventory.equip_item_from_inventory(
        db=db,
        character_id=current_character.id,
        inventory_item_id=inventory_item_id,
        target_slot=target_slot_from_payload
    )

    if not updated_inv_item and not message.lower().endswith("already equipped.") and not message.lower().startswith("item not found"): # Distinguish not found vs other errors
        # A more robust error check is needed here. If equip_item_from_inventory returns None but a real error message,
        # it's an issue. If it returns None and "item not found", it's a 404.
        # For now, assume if updated_inv_item is None and it's not "already equipped", it's a failure.
        # This logic needs refinement based on how crud function signals true errors vs valid "cannot equip" scenarios.
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


    # If successful or "already equipped", we could return the new inventory state or just the message.
    # For now, let's just return the message. The client can re-fetch inventory if needed.
    # To provide full context, we'd fetch the current room as well.
    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=current_character.current_room_id)
    if not current_room_orm: # Should not happen if character is valid
        current_room_schema = None
    else:
        current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)
        
    return schemas.CommandResponse(
        message_to_player=message,
        room_data=current_room_schema # Provide current room context
    )


@router.post("/unequip/{inventory_item_id}", response_model=schemas.CommandResponse) # Using CommandResponse for feedback
def unequip_inventory_item_api(
    inventory_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_character: models.Character = Depends(get_current_active_character),
):
    """
    Unequip an item, moving it back to the backpack.
    inventory_item_id is the UUID of the CharacterInventoryItem entry.
    """
    updated_inv_item, message = crud.crud_character_inventory.unequip_item_to_inventory(
        db=db,
        character_id=current_character.id,
        inventory_item_id=inventory_item_id
    )

    if not updated_inv_item and not message.lower().endswith("not currently equipped.") and not message.lower().startswith("item not found"):
        # Similar to equip, needs better error handling from CRUD
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    current_room_orm = crud.crud_room.get_room_by_id(db, room_id=current_character.current_room_id)
    if not current_room_orm:
        current_room_schema = None
    else:
        current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)

    return schemas.CommandResponse(
        message_to_player=message,
        room_data=current_room_schema
    )