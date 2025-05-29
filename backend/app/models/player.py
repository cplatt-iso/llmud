# backend/app/models/player.py
import uuid
from typing import Optional, List # List for future relationship typing

from sqlalchemy import Column, String # Keep Column for __tablename__ etc.
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship # Import Mapped, mapped_column

from ..db.base_class import Base

class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Relationships (Example for future) ---
    # If a Player can have multiple Characters:
    # characters: Mapped[List["Character"]] = relationship(back_populates="owner")
    # Note: Use "Character" as a string if Character class is defined later or in another file to avoid circular imports.

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, username='{self.username}')>"