# backend/app/schemas/command.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from .room import RoomInDB

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    room_data: Optional[RoomInDB] = None
    message_to_player: Optional[str] = None
    combat_over: bool = False # True if combat resolved (death, flee)
    special_payload: Optional[Dict[str, Any]] = None
    # Add other potential fields for game state updates if needed for HTTP path