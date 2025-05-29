# backend/app/models/character.py
import uuid
from typing import Optional, List, TYPE_CHECKING # Added List, TYPE_CHECKING

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .player import Player # For type hint if using string before
    from .room import Room   # For type hint if using string before
    from .character_inventory_item import CharacterInventoryItem # <<< ADDED

class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False, default="Adventurer")

    player_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("players.id"), nullable=False, index=True)
    current_room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, index=True)

    # --- Inventory Relationship --- (<<< ADDED)
    inventory_items: Mapped[List["CharacterInventoryItem"]] = relationship(
        back_populates="character", 
        cascade="all, delete-orphan" # If character is deleted, their inventory items are also deleted.
    )
    
    # --- Relationships (Example with Mapped type hints) ---
    # owner: Mapped["Player"] = relationship(back_populates="characters") 
    # current_room: Mapped["Room"] = relationship()

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}', player_id='{self.player_id}')>"