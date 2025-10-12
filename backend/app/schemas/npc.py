# backend/app/schemas/npc.py
import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

# --- NpcTemplate Schemas ---


class NpcTemplateBase(BaseModel):
    unique_name_tag: str = Field(
        ..., description="Unique identifier tag for this NPC template."
    )
    name: str
    description: Optional[str] = None
    npc_type: str
    personality_prompt: Optional[str] = None
    dialogue_lines_static: Optional[List[str]] = None
    shop_inventory: Optional[List[str]] = None


class NpcTemplateCreate(NpcTemplateBase):
    pass


class NpcTemplateUpdate(NpcTemplateBase):
    pass


class NpcTemplateInDB(NpcTemplateBase):
    id: uuid.UUID

    class Config:
        from_attributes = True


# --- RoomNpcInstance Schemas (We'll need this soon) ---


# This represents an NPC that is actually placed in a room.
# For now, it's very simple, but it could hold state later (e.g., last_spoken_at).
class RoomNpcInstance(BaseModel):
    room_id: uuid.UUID
    npc_template: NpcTemplateInDB  # Embed the full template detail
