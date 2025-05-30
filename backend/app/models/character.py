# backend/app/models/character.py
import uuid
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    player_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("players.id"), nullable=False, index=True)
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

    inventory_items: Mapped[List["CharacterInventoryItem"]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}', class='{self.class_name}', level={self.level}, hp={self.current_health}/{self.max_health})>"