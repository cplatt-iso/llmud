# backend/app/schemas/player.py
from typing import Optional
import uuid
from pydantic import BaseModel, Field, EmailStr

# --- Base Schemas ---

class PlayerBase(BaseModel):
    """
    Core attributes for a player. Used for reading and as a base for creation.
    """
    username: str = Field(..., min_length=3, max_length=100)
    is_sysop: bool = False
    # email: Optional[EmailStr] = None

class PlayerCreate(PlayerBase):
    """
    Schema for creating a new player. Requires a password.
    """
    # Inherits username and is_sysop from PlayerBase
    password: str = Field(..., min_length=8)

# --- Update Schema (The Fix) ---

class PlayerUpdate(BaseModel):
    """
    Schema for updating a player. All fields are optional.
    This does NOT inherit from PlayerBase to avoid type conflicts.
    """
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    password: Optional[str] = Field(None, min_length=8) # For password change
    is_sysop: Optional[bool] = None

# --- Database and Response Schemas ---

class PlayerInDBBase(PlayerBase):
    """
    Base schema for players as they exist in the database.
    """
    id: uuid.UUID

    class Config:
        from_attributes = True

class Player(PlayerInDBBase):
    """
    Schema for returning player information to the client (e.g., in a GET request).
    Does not include sensitive info like the hashed password.
    """
    pass

class PlayerInDB(PlayerInDBBase):
    """
    Complete schema for a player in the database, including the hashed password.
    This should only be used internally within your application.
    """
    hashed_password: str