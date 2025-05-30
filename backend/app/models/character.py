# backend/app/models/character.py
import uuid
from typing import Optional, List, TYPE_CHECKING 

from sqlalchemy import Column, String, ForeignKey, Integer # Added Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .player import Player 
    from .room import Room   
    from .character_inventory_item import CharacterInventoryItem


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False, default="Adventurer")

    player_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("players.id"), nullable=False, index=True)
    current_room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, index=True)

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
    current_mana: Mapped[int] = mapped_column(Integer, default=10, nullable=False) # Assuming we'll have it
    max_mana: Mapped[int] = mapped_column(Integer, default=10, nullable=False)     # Assuming we'll have it

    # --- Progression ---
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    experience_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- Skills & Traits ---
    learned_skills: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, comment="List of skill identifiers learned by the character")
    learned_traits: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True, comment="List of trait identifiers acquired by the character")


    # --- Basic Combat Stats (Placeholders until derived from gear/attributes) ---
    # These are temporary stand-ins. Real stats will be calculated from attributes + equipment.
    base_ac: Mapped[int] = mapped_column(Integer, default=10, nullable=False, comment="Base Armor Class")
    base_attack_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Base to-hit bonus")
    base_damage_dice: Mapped[str] = mapped_column(String(20), default="1d4", nullable=False, comment="e.g., 1d6")
    base_damage_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Base flat damage bonus")
    
    # --- Inventory Relationship --- 
    inventory_items: Mapped[List["CharacterInventoryItem"]] = relationship(
        back_populates="character", 
        cascade="all, delete-orphan" 
    )
    
    # --- Relationships (Example with Mapped type hints) ---
    # owner: Mapped["Player"] = relationship(back_populates="characters") 
    # current_room: Mapped["Room"] = relationship()

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}', player_id='{self.player_id}', level={self.level}, hp={self.current_health}/{self.max_health})>"