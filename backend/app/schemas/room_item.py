# backend/app/schemas/room_item.py
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .item import Item # Import the Item schema for nesting

class RoomItemInstanceBase(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(1, ge=1)
    properties_override: Optional[Dict[str, Any]] = None

class RoomItemInstanceCreate(RoomItemInstanceBase):
    # room_id will be supplied by the service/path
    # dropped_by_character_id can be optional
    dropped_by_character_id: Optional[uuid.UUID] = None

class RoomItemInstanceUpdate(BaseModel): # For potential future use
    quantity: Optional[int] = Field(None, ge=1)
    properties_override: Optional[Dict[str, Any]] = None

class RoomItemInstanceInDBBase(RoomItemInstanceBase):
    id: uuid.UUID # The unique ID of this room item instance
    room_id: uuid.UUID
    dropped_at: datetime
    dropped_by_character_id: Optional[uuid.UUID] = None
    
    item: Item # Include full item details from the Item template

    class Config:
        from_attributes = True

class RoomItemInstance(RoomItemInstanceInDBBase): # For returning to client
    pass

# Schema for displaying items in a room (could be part of a larger RoomDetail schema)
class RoomItemsView(BaseModel):
    items_on_ground: List[RoomItemInstance] = Field(default_factory=list)