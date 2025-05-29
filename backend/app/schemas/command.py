# backend/app/schemas/command.py
from pydantic import BaseModel
from typing import Optional
from .room import RoomInDB # Import RoomInDB from room.py

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    room_data: Optional[RoomInDB] = None
    message_to_player: Optional[str] = None
    # Future fields: error_code, character_updates, inventory_updates, etc.