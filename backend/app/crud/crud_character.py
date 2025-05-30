# backend/app/crud/crud_character.py
from sqlalchemy.orm import Session
import uuid
from typing import Optional, List

from .. import models, schemas 

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
    db_character_data = character_in.model_dump(exclude_unset=True) # Use exclude_unset for optional fields
    
    # Initialize base stats and vitals.
    # If character_in provides stats, they will override these defaults due to **db_character_data later.
    # Otherwise, model defaults will be used.
    # For now, model defaults are fine. Later, class templates will drive this.
    
    # Example: if we wanted to calculate max_health based on constitution here:
    # con = db_character_data.get('constitution', 10) # Get from input or default
    # max_hp = 10 + ( (con - 10) // 2 ) * 1 # Basic D&D style HP calculation per level (level 1 here)
    # if max_hp < 1: max_hp = 1
    # db_character_data['max_health'] = max_hp
    # db_character_data['current_health'] = max_hp
    # Similar for mana if based on intelligence.
    # For now, we rely on the model's direct defaults set in character.py

    db_character = models.Character(
        **db_character_data, 
        player_id=player_id, 
        current_room_id=initial_room_id,
        learned_skills=[], # Explicitly initialize as empty list
        learned_traits=[]  # Explicitly initialize as empty list
        # Model defaults will handle other stats if not in db_character_data
    )
    
    db.add(db_character)
    db.commit()
    db.refresh(db_character)
    return db_character

def update_character_room(db: Session, character_id: uuid.UUID, new_room_id: uuid.UUID) -> Optional[models.Character]:
    db_character = get_character(db, character_id=character_id)
    if db_character:
        db_character.current_room_id = new_room_id # Direct assignment is fine
        db.add(db_character) # Add to session to mark as dirty
        db.commit()
        db.refresh(db_character)
        return db_character
    return None

def update_character_health(db: Session, character_id: uuid.UUID, amount_change: int) -> Optional[models.Character]:
    """Updates character's current health by amount_change. Clamps between 0 and max_health."""
    character = get_character(db, character_id=character_id)
    if not character:
        return None
    
    character.current_health += amount_change
    if character.current_health < 0:
        character.current_health = 0
    if character.current_health > character.max_health:
        character.current_health = character.max_health
        
    db.add(character)
    db.commit()
    db.refresh(character)
    return character

def add_experience(db: Session, character_id: uuid.UUID, amount: int) -> Optional[models.Character]:
    """Adds experience points to a character. Level up logic to be implemented later."""
    character = get_character(db, character_id=character_id)
    if not character or amount <=0: # No negative XP for now, you cheapskate
        return character # Or None if char not found

    character.experience_points += amount
    # TODO: Implement level_up_character(db, character) call here if XP crosses threshold
    # For now, just adding XP.
    
    db.add(character)
    db.commit()
    db.refresh(character)
    return character

# Conceptual: def level_up_character(db: Session, character: models.Character): ...