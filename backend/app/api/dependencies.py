# backend/app/api/dependencies.py
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app import models, schemas, crud
from app.db.session import get_db
from app.game_state import active_game_sessions # <<< ADDED THIS IMPORT

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/users/login"
)

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY

async def get_current_player(
    db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> models.Player:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username_or_player_id: Optional[str] = payload.get("sub")
        if username_or_player_id is None:
            raise credentials_exception
        
        try:
            player_uuid = uuid.UUID(username_or_player_id)
        except ValueError:
            print(f"Error: Subject '{username_or_player_id}' in token is not a valid UUID.")
            raise credentials_exception
            
    except JWTError as e:
        print(f"JWTError during token decode: {e}")
        raise credentials_exception
    
    player = crud.crud_player.get_player(db, player_id=player_uuid)
    if player is None:
        raise credentials_exception
    return player

async def get_current_active_character( # <<< NEW DEPENDENCY
    db: Session = Depends(get_db),
    current_player: models.Player = Depends(get_current_player)
) -> models.Character:
    character_id = active_game_sessions.get(current_player.id)
    
    if not character_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="No active character selected for this session. Please select a character.",
        )
    
    character = crud.crud_character.get_character(db, character_id=character_id)
    if not character:
        # This case implies data inconsistency or character deleted after selection.
        # Clear stale entry from active_game_sessions.
        active_game_sessions.pop(current_player.id, None)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active character with ID {character_id} not found. Session reset.",
        )

    # This check is crucial for data integrity, though selection process should ensure it.
    if character.player_id != current_player.id:
        active_game_sessions.pop(current_player.id, None) # Clear inconsistent state
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CRITICAL: Active character's player ID does not match authenticated player. Session reset.",
        )
        
    return character