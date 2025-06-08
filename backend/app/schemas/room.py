# backend/app/schemas/room.py
import uuid
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ..models.room import RoomTypeEnum
from .common_structures import ExitDetail, InteractableDetail
from .npc import NpcTemplateInDB # Import this properly now
from .item import RoomItemInstanceInDB
from .mob import RoomMobInstance
from .character import Character


# --- Room Schemas ---

# This is the base for what constitutes a "Room" in its simplest form.
class RoomBase(BaseModel):
    name: str
    description: Optional[str] = None
    x: int
    y: int
    z: int
    room_type: RoomTypeEnum = Field(default=RoomTypeEnum.STANDARD)

# This schema is specifically for CREATING rooms from the seeder JSON.
# It must match the structure of the "data" block in rooms_z0.json exactly.
class RoomCreate(RoomBase):
    exits: Optional[Dict[str, Any]] = Field(default_factory=dict)
    interactables: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    npc_placements: Optional[List[str]] = Field(default_factory=list)
    # Note: We use Dict[str, Any] for exits/interactables here because the seeder
    # does its own detailed Pydantic validation later. This schema is just for capture.

# This is for PARTIAL updates, e.g., via an API endpoint.
class RoomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    exits: Optional[Dict[str, ExitDetail]] = None
    interactables: Optional[List[InteractableDetail]] = None
    room_type: Optional[RoomTypeEnum] = None
    npc_placements: Optional[List[str]] = None # Allow updating placements via API too

# This is the full representation of a Room as it exists in the database,
# including all relationships, for sending to the client.
class RoomInDB(RoomBase):
    id: uuid.UUID
    exits: Optional[Dict[str, ExitDetail]] = Field(default_factory=dict)
    interactables: Optional[List[InteractableDetail]] = Field(default_factory=list)
    items_on_ground: List[RoomItemInstanceInDB] = []
    mobs_in_room: List[RoomMobInstance] = []
    other_characters: List[Character] = []
    npcs_in_room: List[NpcTemplateInDB] = [] # This is now correct because of the import
    dynamic_description_additions: List[str] = []

    class Config:
        from_attributes = True