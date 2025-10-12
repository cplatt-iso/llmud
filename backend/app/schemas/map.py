# backend/app/schemas/map.py (NEW FILE)
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..models.room import RoomTypeEnum
from .room import (  # We'll use the existing RoomInDB for individual room details
    RoomInDB,
)


class MapRoomData(BaseModel):
    id: uuid.UUID
    x: int
    y: int
    name: Optional[str] = None  # Optional: for tooltips or labels
    exits: Optional[Dict[str, str]] = Field(default_factory=dict)
    is_current_room: bool = False
    is_visited: bool = True  # For now, all fetched rooms are considered visited
    room_type: RoomTypeEnum


class MapLevelDataResponse(BaseModel):
    z_level: int
    current_room_id: uuid.UUID
    rooms: List[MapRoomData]
    current_zone_name: Optional[str] = None
    current_zone_level_range: Optional[str] = None
