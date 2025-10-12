# backend/app/crud/crud_player.py
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.security import get_password_hash


def get_player(db: Session, player_id: uuid.UUID) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.id == player_id).first()


def get_player_by_username(db: Session, username: str) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.username == username).first()


def count_players(db: Session) -> int:
    """Counts the total number of players in the database."""
    return db.query(models.Player.id).count()


def create_player(
    db: Session, *, player_in: schemas.PlayerCreate, is_sysop: bool = False
) -> models.Player:
    """
    Creates a new player.
    Accepts an is_sysop flag to explicitly set the user's admin status.
    """
    hashed_password = get_password_hash(player_in.password)

    # <<< THE FIX IS HERE >>>
    # We must also exclude 'is_sysop' from the dump, because we are supplying it manually.
    db_player_data = player_in.model_dump(exclude={"password", "is_sysop"})

    # Now, the **db_player_data will NOT contain 'is_sysop', preventing the conflict.
    db_player = models.Player(
        **db_player_data, hashed_password=hashed_password, is_sysop=is_sysop
    )

    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player
