# backend/app/crud/crud_player.py
from sqlalchemy.orm import Session
import uuid # Ensure uuid is imported
from typing import Optional

from .. import models, schemas # models.Player, schemas.PlayerCreate etc.
from ..core.security import get_password_hash # Our password hashing utility

def get_player(db: Session, player_id: uuid.UUID) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.id == player_id).first()

def get_player_by_username(db: Session, username: str) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.username == username).first()

def create_player(db: Session, *, player_in: schemas.PlayerCreate) -> models.Player:
    hashed_password = get_password_hash(player_in.password)
    # Create a dictionary for the DB model, excluding the plain password
    db_player_data = player_in.model_dump(exclude={'password'})
    db_player = models.Player(**db_player_data, hashed_password=hashed_password)
    
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player