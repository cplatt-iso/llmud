# backend/app/schemas/command.py
import uuid  # <<< Import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel

from .room import RoomInDB


class CommandRequest(BaseModel):
    command: str


class LocationUpdate(BaseModel):
    """A small model to carry location update info."""

    character_id: uuid.UUID
    new_room_id: uuid.UUID


class CommandResponse(BaseModel):
    room_data: Optional[RoomInDB] = None
    message_to_player: Optional[str] = None
    combat_over: bool = False
    special_payload: Optional[Dict[str, Any]] = None

    # --- THE NEW FIELD ---
    # This will be populated by commands that change a character's location.
    location_update: Optional[LocationUpdate] = None
