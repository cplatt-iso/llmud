# backend/app/api/v1/endpoints/inventory.py
import uuid
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .... import crud, models, schemas
from ....api.dependencies import get_current_active_character
from ....db.session import get_db
from ....ws_command_parsers.ws_interaction_parser import (  # IMPORT THE HELPER
    _send_inventory_update_to_player,
)

router = APIRouter()


def format_inventory_for_display(
    inventory_items: List[models.CharacterInventoryItem],
    character: models.Character,  # Add character for currency
) -> schemas.CharacterInventoryDisplay:
    """Helper function to format raw inventory items into the display schema."""
    equipped_dict: dict[str, schemas.CharacterInventoryItem] = {}  # Use correct schema
    backpack_list: list[schemas.CharacterInventoryItem] = []  # Use correct schema

    for inv_item_orm in inventory_items:
        # Ensure the item relationship is loaded for the schema conversion
        # This should be handled by the query that fetches inventory_items_orm
        # (e.g., crud.crud_character_inventory.get_character_inventory)
        if not inv_item_orm.item:  # Defensive check
            # logger.warning(f"Inventory item {inv_item_orm.id} missing item details, skipping in display.")
            continue
        item_schema = schemas.CharacterInventoryItem.from_orm(
            inv_item_orm
        )  # Use correct schema
        if inv_item_orm.equipped and inv_item_orm.equipped_slot:
            equipped_dict[inv_item_orm.equipped_slot] = item_schema
        else:
            backpack_list.append(item_schema)

    return schemas.CharacterInventoryDisplay(
        equipped_items=equipped_dict,
        backpack_items=backpack_list,
        platinum=character.platinum_coins,
        gold=character.gold_coins,
        silver=character.silver_coins,
        copper=character.copper_coins,
    )


@router.get("/mine", response_model=schemas.CharacterInventoryDisplay)
def get_my_inventory(  # This can remain synchronous as it's read-only
    db: Session = Depends(get_db),
    current_character: models.Character = Depends(get_current_active_character),
):
    """
    Retrieve the inventory for the currently active character.
    """
    inventory_items_orm = crud.crud_character_inventory.get_character_inventory(
        db, character_id=current_character.id
    )
    # Pass current_character to include currency
    return format_inventory_for_display(inventory_items_orm, current_character)


@router.post("/equip/{inventory_item_id}", response_model=schemas.CommandResponse)
async def equip_inventory_item_api(  # MAKE ASYNC
    inventory_item_id: uuid.UUID,
    payload: schemas.EquipRequest = Body(None),
    db: Session = Depends(get_db),
    current_character: models.Character = Depends(get_current_active_character),
):
    target_slot_from_payload = payload.target_slot if payload else None

    updated_inv_item, message = crud.crud_character_inventory.equip_item_from_inventory(
        db=db,
        character_obj=current_character,
        inventory_item_id=inventory_item_id,
        target_slot=target_slot_from_payload,
    )

    if (
        not updated_inv_item
        and not message.lower().endswith("already equipped.")
        and not message.lower().startswith("item not found")
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    if updated_inv_item:
        db.commit()
        db.refresh(updated_inv_item)  # Refresh the specific item
        db.refresh(current_character)  # Refresh character for currency and other stats
        await _send_inventory_update_to_player(db, current_character)  # SEND WS UPDATE
    # else: db.rollback() # If no update, ensure no lingering changes

    current_room_orm = crud.crud_room.get_room_by_id(
        db, room_id=current_character.current_room_id
    )
    current_room_schema = None
    if current_room_orm:
        current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)

    return schemas.CommandResponse(
        message_to_player=message, room_data=current_room_schema
    )


@router.post("/unequip/{inventory_item_id}", response_model=schemas.CommandResponse)
async def unequip_inventory_item_api(  # MAKE ASYNC
    inventory_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_character: models.Character = Depends(get_current_active_character),
):
    updated_inv_item, message = crud.crud_character_inventory.unequip_item_to_inventory(
        db=db,
        character_obj=current_character,
        inventory_item_id=inventory_item_id,  # Pass inventory_item_id directly
    )

    if (
        not updated_inv_item
        and not message.lower().endswith("not currently equipped.")
        and not message.lower().startswith("item not found")
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    if updated_inv_item:
        db.commit()
        db.refresh(updated_inv_item)  # Refresh the specific item
        db.refresh(current_character)  # Refresh character for currency and other stats
        await _send_inventory_update_to_player(db, current_character)  # SEND WS UPDATE
    # else: db.rollback() # If no update, ensure no lingering changes

    current_room_orm = crud.crud_room.get_room_by_id(
        db, room_id=current_character.current_room_id
    )
    current_room_schema = None
    if current_room_orm:
        current_room_schema = schemas.RoomInDB.from_orm(current_room_orm)

    return schemas.CommandResponse(
        message_to_player=message, room_data=current_room_schema
    )
