# backend/app/models/character.py
import uuid
from typing import Optional # For optional types

from sqlalchemy import Column, String, ForeignKey # Keep Column for __tablename__ etc.
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship # Import Mapped, mapped_column

from ..db.base_class import Base
# If you need to type hint relationships to Player or Room and they are in other files:
# from .player import Player # Example, adjust path if needed
# from .room import Room   # Example, adjust path if needed

class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    class_name: Mapped[str] = mapped_column(String(50), nullable=False, default="Adventurer")

    # Foreign Key to link to the Player (User account)
    player_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("players.id"), nullable=False, index=True)
    
    # Foreign Key to link to the Character's current Room
    current_room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False, index=True)

    # --- Relationships (Example with Mapped type hints) ---
    # owner: Mapped["Player"] = relationship(back_populates="characters") 
    # current_room: Mapped["Room"] = relationship()
    # Using string "Player" and "Room" for forward references if classes are in different files or defined later.
    # If they are imported, you can use Player and Room directly.

    def __repr__(self) -> str:
        # Accessing self.id, self.name, self.player_id should give the actual values here
        return f"<Character(id={self.id}, name='{self.name}', player_id='{self.player_id}')>"