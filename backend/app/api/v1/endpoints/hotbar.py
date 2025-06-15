# Create this new file: backend/app/api/v1/endpoints/hotbar.py

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session, attributes

from .... import schemas, models, crud
from ....db.session import get_db
from ....api.dependencies import get_current_active_character

logger = logging.getLogger(__name__)
router = APIRouter()

class HotbarSlotUpdatePayload(BaseModel):
    type: str # "item" or "skill"
    identifier: str # item's template_id or skill's id_tag
    name: str # for display

@router.post("/hotbar/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_hotbar_slot(
    slot_id: int,
    payload: Optional[HotbarSlotUpdatePayload] = Body(None), # Payload is optional to allow clearing a slot
    db: Session = Depends(get_db),
    character: models.Character = Depends(get_current_active_character)
):
    """
    Sets or clears a specific slot on the character's hotbar.
    """
    if not (1 <= slot_id <= 10):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid slot ID. Must be between 1 and 10.")

    # Initialize current_hotbar with default empty slots and the correct type
    current_hotbar: Dict[str, Optional[Dict[str, Any]]] = {
        str(i): None for i in range(1, 11)
    }

    # If character has an existing hotbar, merge its contents
    if character.hotbar:
        # character.hotbar could be a SQLAlchemy MutableDict or similar.
        # We iterate over its items (making a copy if it's mutable)
        # and populate our well-typed current_hotbar.
        for key, value in dict(character.hotbar).items():
            str_key = str(key)
            # Only update slots that are part of the defined 1-10 range
            if str_key in current_hotbar:
                current_hotbar[str_key] = value
    
    # Update the specific slot
    current_hotbar[str(slot_id)] = payload.model_dump() if payload else None

    # Assign the modified dictionary back to the character's hotbar property
    character.hotbar = current_hotbar
    # Flag it as modified for SQLAlchemy's change detection
    attributes.flag_modified(character, "hotbar")

    db.add(character)
    db.commit()

    return