# backend/app/models/character_inventory_item.py
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base_class import Base

if TYPE_CHECKING:
    from .character import Character  # noqa: F401
    from .item import Item  # noqa: F401


class CharacterInventoryItem(Base):
    __tablename__ = "character_inventory_items"

    # Composite Primary Key: (character_id, item_id)
    # However, SQLAlchemy prefers a single surrogate primary key for association objects
    # if they have additional attributes beyond just the foreign keys.
    # Let's add an explicit id for this table for easier reference, though character_id + item_id could form a unique constraint.
    # Or, if an item can appear multiple times (e.g. two identical non-stackable swords),
    # then an auto-incrementing ID for this table row is essential.
    # Let's assume for now a character can only have ONE "entry" for a given item_id, and quantity handles multiples if stackable.
    # If not stackable, and they have two of the same sword, they'd be two separate Item instances in the Item table (e.g. with serial numbers or unique IDs anyway).
    # For our MUD, usually an Item is a "template". If a player has two "Long Sword" (same item_id), this table handles it.
    # Okay, if Item.stackable is false, each instance is a separate row here with quantity 1.
    # If Item.stackable is true, one row with quantity > 1.
    # Let's give this table its own UUID PK for simplicity in referencing a specific *instance* in inventory.

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique ID for this specific instance of an item in a character's inventory",
    )

    character_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id"), index=True, nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("items.id"), index=True, nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Indicates if this specific inventory item instance is currently equipped
    equipped: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    # If equipped, this specifies which of the character's equipment slots it occupies.
    # This must be one of the keys from models.item.EQUIPMENT_SLOTS.
    # Necessary for items that can fit into more than one type of slot (e.g. generic 'ring' item into 'finger_1' or 'finger_2')
    # or to distinguish main_hand vs off_hand for identical weapons.
    equipped_slot: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Actual character slot occupied if equipped, e.g. 'finger_1'",
    )

    # Relationships
    character: Mapped["Character"] = relationship(back_populates="inventory_items")
    item: Mapped["Item"] = (
        relationship()
    )  # No back_populates needed if Item doesn't need to know all its inventory entries directly

    def __repr__(self) -> str:
        return f"<CharInvItem(id={self.id}, char_id='{self.character_id}', item_id='{self.item_id}', qty={self.quantity}, equipped={self.equipped}, slot='{self.equipped_slot}')>"
