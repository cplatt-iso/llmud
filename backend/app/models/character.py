# backend/app/models/character.py
import uuid
from typing import Any, Dict, Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app import models

from ..db.base_class import Base

if TYPE_CHECKING:
    from .player import Player
    from .room import Room
    from .character_inventory_item import CharacterInventoryItem
    from .character_class_template import CharacterClassTemplate # <<< NEW IMPORT

class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False, default="Adventurer") # Keep as stored field
    owner: Mapped["Player"] = relationship(back_populates="characters", lazy="joined") 

    player_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("players.id"), nullable=False, index=True)
    god_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="0 for mortals, 1-10 for gods")
    titles: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=lambda: [], comment="e.g., ['The Godslayer', 'Cheesewheel Enthusiast']")
    current_room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, index=True)

    # --- Class Template Link ---
    character_class_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("character_class_templates.id"),
        nullable=True
    )
    # Optional: if you want to access the template object directly.
    # `lazy="joined"` can be good if you always need it, but selective loading might be better.
    class_template_ref: Mapped[Optional["CharacterClassTemplate"]] = relationship(foreign_keys=[character_class_template_id])


    # --- Core Attributes ---
    strength: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    dexterity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    constitution: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    wisdom: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    charisma: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    luck: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # --- Combat/Vital Stats ---
    current_health: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_health: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    current_mana: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_mana: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # --- Progression ---
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    experience_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- Skills & Traits ---
    learned_skills: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=lambda: [])
    learned_traits: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, default=lambda: [])

    # --- Basic Combat Stats (Placeholders until derived from gear/attributes) ---
    base_ac: Mapped[int] = mapped_column(Integer, default=10, nullable=False, comment="Base Armor Class")
    base_attack_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Base to-hit bonus")
    base_damage_dice: Mapped[str] = mapped_column(String(20), default="1d4", nullable=False, comment="e.g., 1d6")
    base_damage_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Base flat damage bonus")

    platinum_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gold_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    silver_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    copper_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    inventory_items: Mapped[List["CharacterInventoryItem"]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan"
    )

    def get_attribute_modifier(self, attribute_name: str) -> int:
        """Calculates the D&D-style modifier for a given attribute."""
        score = getattr(self, attribute_name, 10) # Default to 10 if attribute somehow not found
        return (score - 10) // 2

    def get_equipped_items_by_slot(self, slot_key: str) -> List['CharacterInventoryItem']: # type: ignore
        """Returns a list of items equipped in the specified slot."""
        if not hasattr(self, 'inventory_items') or not self.inventory_items:
            return []
        return [inv_item for inv_item in self.inventory_items if inv_item.equipped and inv_item.equipped_slot == slot_key]

    def calculate_combat_stats(self) -> Dict[str, Any]:
        stats = {
            "effective_ac": 10, 
            "attack_bonus": 0,
            "damage_dice": "1d2", # <<< CHANGED UNARMED TO 1d2 FROM 1d4
            "damage_bonus": 0,
            "primary_attribute_for_attack": "strength"
        }

        dex_modifier = self.get_attribute_modifier("dexterity")
        str_modifier = self.get_attribute_modifier("strength") # Calculate once

        # Initialize AC with base + dex_modifier
        # This initial_ac_with_dex will be adjusted if armor caps dex_modifier
        initial_ac_with_dex = 10 + dex_modifier
        current_ac = initial_ac_with_dex # Start with this

        equipped_weapon_item: Optional[models.Item] = None # Store the Item model directly
        max_dex_bonus_cap_from_armor: Optional[int] = None

        # Ensure inventory_items is accessible and not None
        # The relationship should be loaded. If it's not, that's a different problem (lazy loading config)
        # but usually `self.inventory_items` would work if the character ORM object is complete.
        if not hasattr(self, 'inventory_items') or self.inventory_items is None:
            # This case should ideally not happen if the character object is properly loaded.
            # If it does, we proceed with base stats.
            print(f"Warning: Character {self.name} has no inventory_items attribute or it's None during stat calculation.")
        else:
            for inv_item in self.inventory_items:
                if not inv_item.equipped or not inv_item.item:
                    continue

                item_model = inv_item.item # This is the actual Item model instance
                item_props = item_model.properties or {}

                # Armor Class contributions from armor AND shields
                if item_model.item_type == "armor": # This covers torso, head, feet, etc. AND shields if type is "armor"
                    current_ac += item_props.get("armor_class_bonus", 0)
                    
                    # Check for max_dex_bonus cap from this piece of armor
                    if "max_dex_bonus_to_ac" in item_props:
                        cap = item_props["max_dex_bonus_to_ac"]
                        if max_dex_bonus_cap_from_armor is None or cap < max_dex_bonus_cap_from_armor:
                            max_dex_bonus_cap_from_armor = cap
                
                # Specifically identify the main hand weapon
                if inv_item.equipped_slot == "main_hand" and item_model.item_type == "weapon":
                    equipped_weapon_item = item_model
        
        # After iterating all items, apply the Max Dex Bonus cap if one was found
        if max_dex_bonus_cap_from_armor is not None:
            # We started with current_ac = 10 + dex_modifier
            # If dex_modifier exceeds cap, we need to subtract the excess
            if dex_modifier > max_dex_bonus_cap_from_armor:
                excess_dex = dex_modifier - max_dex_bonus_cap_from_armor
                current_ac -= excess_dex
        
        stats["effective_ac"] = current_ac

        # Determine Attack and Damage
        if equipped_weapon_item:
            weapon_props = equipped_weapon_item.properties or {}
            stats["damage_dice"] = weapon_props.get("damage", "1d2") # Default to unarmed if weapon has no damage prop

            is_finesse = weapon_props.get("finesse", False)
            attack_attribute_modifier = str_modifier
            if is_finesse and dex_modifier > str_modifier:
                attack_attribute_modifier = dex_modifier
                stats["primary_attribute_for_attack"] = "dexterity"
            else:
                stats["primary_attribute_for_attack"] = "strength"
            
            stats["attack_bonus"] = attack_attribute_modifier + weapon_props.get("attack_bonus", 0)
            stats["damage_bonus"] = attack_attribute_modifier + weapon_props.get("damage_bonus", 0)
        else:
            # Unarmed: Already set damage_dice to "1d2". Bonus is Str mod.
            stats["attack_bonus"] = str_modifier
            stats["damage_bonus"] = str_modifier
            stats["primary_attribute_for_attack"] = "strength"

        # Add character's general base_attack_bonus (e.g. from level/class BAB)
        stats["attack_bonus"] += self.base_attack_bonus 
        # Note: self.base_damage_bonus is NOT added here if using weapon, as it's part of unarmed calculation.
        # If it were a generic +damage bonus for all attacks, it would be added.

        return stats

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}', class='{self.class_name}', level={self.level}, hp={self.current_health}/{self.max_health})>"