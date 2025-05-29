# backend/app/schemas/room.py
from pydantic import BaseModel, Field, field_validator # field_validator for Pydantic v2
import uuid # Import uuid
from typing import Dict, Optional, Any

class RoomBase(BaseModel):
    name: str
    description: Optional[str] = None
    x: int
    y: int
    z: int
    # Exits: keys are directions (str), values are target room UUIDs (str)
    exits: Optional[Dict[str, str]] = Field(default_factory=dict) 

class RoomCreate(RoomBase):
    # id can optionally be provided if you want to set it explicitly,
    # otherwise the DB model's default=uuid.uuid4 will handle it.
    id: Optional[uuid.UUID] = None 
    # name, description, x, y, z, exits are inherited
    pass

class RoomUpdate(BaseModel): # Not heavily used yet, but good to keep consistent
    name: Optional[str] = None
    description: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    z: Optional[int] = None
    exits: Optional[Dict[str, str]] = None

class RoomInDB(RoomBase): # This schema is used for reading rooms from DB
    id: uuid.UUID # ID from DB will definitely be a UUID

    class Config:
        from_attributes = True # For Pydantic v2 ORM mode
