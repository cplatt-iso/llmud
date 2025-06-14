# backend/app/models/item.py
import uuid
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Text, Float, JSON, Integer, Boolean # Keep Column for __tablename__ etc.
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    item_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False, comment="e.g., weapon, armor, potion, junk")
    # Slot where the item can be equipped. Nullable if not equippable (e.g. potion, junk).
    # Could be a list if an item can fit multiple slots (e.g. 'ring_finger_1', 'ring_finger_2'), or a generic 'ring'
    # For simplicity now, let's assume a single primary slot string, or comma-separated if multiple.
    # Or, better, just 'equippable_slot_type' (e.g. 'weapon', 'head', 'ring') and then CharacterInventoryItem handles specifics.
    # Let's go with a simple slot string for now that defines its primary use.
    rarity: Mapped[str] = mapped_column(String(50), nullable=False, default="common", index=True)
    slot: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="e.g., head, torso, main_hand, off_hand, ring, consumable, utility")
    
    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="e.g., {'damage': '1d6', 'armor_class': 5, 'modifier': {'strength': 1}}")
    
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Monetary value for shops")
    stackable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_stack_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1, comment="Max items in a stack if stackable, 1 if not.")

    # Relationship to CharacterInventoryItem (one-to-many: one Item type can be in many inventories)
    # character_inventory_entries: Mapped[List["CharacterInventoryItem"]] = relationship(back_populates="item")


    def __repr__(self) -> str:
        return f"<Item(id={self.id}, name='{self.name}', type='{self.item_type}')>"

# Define standard equipment slots (could be in config or a helper)
# These are the "logical" slots on a character. An item might be usable in one or more of these.
# This helps in validating equip/unequip operations.
EQUIPMENT_SLOTS = {
    "head": "Head",
    "neck": "Neck",
    "torso": "Torso",
    "back": "Back", # Cloak
    "main_hand": "Main Hand",
    "off_hand": "Off Hand", # Shield or second weapon
    "legs": "Legs",
    "feet": "Feet",
    "wrists": "Wrists",
    "hands": "Hands", # Gloves
    "finger_1": "Finger 1",
    "finger_2": "Finger 2",
    "belt": "Belt", 
    "pipe": "Pipe", # For smoking items, if applicable
    "drugs": "Drugs", # Consumables like potions, elixirs, etc.
    "trinket": "Trinket" # Small items that don't fit other categories
    # "ranged_weapon": "Ranged Weapon",
    # "ammunition": "Ammunition"
}