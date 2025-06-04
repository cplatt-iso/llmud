# backend/app/schemas/room.py
from pydantic import BaseModel, Field
import uuid
from typing import Dict, Optional, Any, List

# Import the new detail schemas and RoomTypeEnum
from ..models.room import RoomTypeEnum # <<< Import from models
from .common_structures import ExitDetail, InteractableDetail

class RoomBase(BaseModel):
    name: str
    description: Optional[str] = None
    x: int
    y: int
    z: int
    room_type: RoomTypeEnum = Field(default=RoomTypeEnum.STANDARD) # <<< NEW FIELD
    exits: Optional[Dict[str, ExitDetail]] = Field(default_factory=dict) 
    interactables: Optional[List[InteractableDetail]] = Field(default_factory=list)

class RoomCreate(RoomBase):
    id: Optional[uuid.UUID] = None 
    pass

class RoomUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    z: Optional[int] = None
    room_type: Optional[RoomTypeEnum] = None # <<< NEW FIELD
    exits: Optional[Dict[str, ExitDetail]] = None
    interactables: Optional[List[InteractableDetail]] = None

class RoomInDB(RoomBase):
    id: uuid.UUID
    # room_type is already in RoomBase

    class Config:
        from_attributes = True