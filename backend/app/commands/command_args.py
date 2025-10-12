# backend/app/commands/command_args.py
from typing import List

from app import models, schemas  # Ensure these are accessible from app root
from pydantic import BaseModel
from sqlalchemy.orm import Session


class CommandContext(BaseModel):
    db: Session
    active_character: models.Character
    current_room_orm: models.Room
    current_room_schema: schemas.RoomInDB
    original_command: str
    command_verb: str
    args: List[str]  # The rest of the command words after the verb
    # For more complex parsing, args could be a pre-parsed Pydantic model itself

    class Config:
        arbitrary_types_allowed = True  # For SQLAlchemy Session and ORM models
