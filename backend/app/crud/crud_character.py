# backend/app/crud/crud_character.py
from sqlalchemy.orm import Session
import uuid
from typing import Optional, List

from .. import models, schemas # models.Character, schemas.CharacterCreate etc.

def get_character(db: Session, character_id: uuid.UUID) -> Optional[models.Character]:
    return db.query(models.Character).filter(models.Character.id == character_id).first()

def get_character_by_name(db: Session, name: str) -> Optional[models.Character]:
    return db.query(models.Character).filter(models.Character.name == name).first()

def get_characters_by_player(db: Session, player_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[models.Character]:
    return db.query(models.Character).filter(models.Character.player_id == player_id).offset(skip).limit(limit).all()

def create_character(
    db: Session, *, 
    character_in: schemas.CharacterCreate, 
    player_id: uuid.UUID, 
    initial_room_id: uuid.UUID
) -> models.Character:
    """
    Create a new character.
    'player_id' and 'initial_room_id' are provided by the service layer, not directly from client request model.
    """
    # Create a dictionary from the Pydantic model
    db_character_data = character_in.model_dump()
    
    db_character = models.Character(
        **db_character_data, 
        player_id=player_id, 
        current_room_id=initial_room_id
    )
    
    db.add(db_character)
    db.commit()
    db.refresh(db_character)
    return db_character

def update_character_room(db: Session, character_id: uuid.UUID, new_room_id: uuid.UUID) -> Optional[models.Character]:
    """
    Updates the character's current room.
    """
    db_character = get_character(db, character_id=character_id)
    if db_character:
        # Use SQLAlchemy's update mechanism to modify the current_room_id
        db.query(models.Character).filter(models.Character.id == character_id).update(
            {models.Character.current_room_id: new_room_id}
        )
        db.commit()
        db.refresh(db_character)
        return db_character
    return None