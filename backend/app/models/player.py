# backend/app/models/player.py
import uuid
from typing import Optional, List, TYPE_CHECKING 
from sqlalchemy import Column, String, Boolean # <-- Import Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING: 
    from .character import Character 

class Player(Base):
    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # --- THE GOD KEY ---
    is_sysop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    characters: Mapped[List["Character"]] = relationship(back_populates="owner")

    def __repr__(self) -> str:
        return f"<Player(id={self.id}, username='{self.username}', sysop={self.is_sysop})>"