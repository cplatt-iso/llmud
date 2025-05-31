# backend/app/schemas/map.py (NEW FILE)
import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from .room import RoomInDB # We'll use the existing RoomInDB for individual room details

class MapRoomData(BaseModel):
    id: uuid.UUID
    x: int
    y: int
    name: Optional[str] = None # Optional: for tooltips or labels
    exits: Optional[Dict[str, str]] = Field(default_factory=dict)
    is_current_room: bool = False
    is_visited: bool = True # For now, all fetched rooms are considered visited

class MapLevelDataResponse(BaseModel):
    z_level: int
    current_room_id: Optional[uuid.UUID] = None
    rooms: List[MapRoomData] = Field(default_factory=list)