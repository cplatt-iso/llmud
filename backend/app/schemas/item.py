# backend/app/schemas/item.py
import uuid
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

# --- Item Schemas ---
class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    item_type: str = Field(..., description="e.g., weapon, armor, potion, junk")
    rarity: str = "common"
    slot: Optional[str] = Field(None, description="Primary equippable slot type, e.g., head, main_hand, consumable")
    properties: Optional[Dict[str, Any]] = Field(None, description="e.g., {'damage': '1d6', 'armor_class': 5}")
    weight: float = Field(0.0, ge=0)
    value: int = Field(0, ge=0)
    stackable: bool = False
    max_stack_size: Optional[int] = Field(1, ge=1)

class RoomItemInstanceBase(BaseModel):
    quantity: int
    item: 'Item' # Use the existing Item schema for the template details

class RoomItemInstanceInDB(RoomItemInstanceBase):
    id: uuid.UUID
    room_id: uuid.UUID
    item_id: uuid.UUID
    
    class Config:
        from_attributes = True
class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel): # Allow partial updates
    name: Optional[str] = None
    description: Optional[str] = None
    item_type: Optional[str] = None
    slot: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    weight: Optional[float] = None
    value: Optional[int] = None
    stackable: Optional[bool] = None
    max_stack_size: Optional[int] = None

class ItemInDBBase(ItemBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

class Item(ItemInDBBase): # For returning item info
    pass

class ItemInDB(ItemInDBBase): # More complete internal representation if needed
    pass


# --- CharacterInventoryItem Schemas ---
# This represents an item *instance* in a character's inventory

class CharacterInventoryItemBase(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(1, ge=1)
    equipped: bool = False
    equipped_slot: Optional[str] = None # Actual character slot occupied if equipped

class CharacterInventoryItemCreate(CharacterInventoryItemBase):
    # character_id will be supplied by the service/path
    pass

class CharacterInventoryItemUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1)
    equipped: Optional[bool] = None
    equipped_slot: Optional[str] = None

class CharacterInventoryItemInDBBase(CharacterInventoryItemBase):
    id: uuid.UUID # The unique ID of this inventory entry
    character_id: uuid.UUID
    item: Item # Include full item details when displaying inventory

    class Config:
        from_attributes = True

class CharacterInventoryItem(CharacterInventoryItemInDBBase): # For returning to client
    pass


# --- Composite Schema for Displaying Full Inventory ---
class CharacterInventoryDisplay(BaseModel):
    equipped_items: Dict[str, CharacterInventoryItem] = Field(default_factory=dict, description="Items currently equipped, keyed by their equipped_slot")
    backpack_items: List[CharacterInventoryItem] = Field(default_factory=list, description="Items in inventory but not equipped")
    platinum: int = 0
    gold: int = 0
    silver: int = 0
    copper: int = 0
    # Add more fields like total_weight, currency later

class EquipRequest(BaseModel):
    target_slot: Optional[str] = Field(None, description="Optional: The specific character slot to equip the item to, e.g., 'finger_1'")