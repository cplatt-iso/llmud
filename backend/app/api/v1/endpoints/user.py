# backend/app/api/v1/endpoints/user.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Form # Added Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Any
from pydantic import BaseModel # Ensure BaseModel is imported
from datetime import timedelta # For token expiration

from app import schemas, crud, models # Import schemas, crud, models
from app.db.session import get_db
from app.core.security import verify_password, create_access_token # Import create_access_token
from app.core.config import settings # For ACCESS_TOKEN_EXPIRE_MINUTES
from app.api.dependencies import get_current_player # Add this import

router = APIRouter() 

class UserLoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=Token)
def login_user_for_access_token(
    db: Session = Depends(get_db), # Removed *, so Form can be injected
    form_data: OAuth2PasswordRequestForm = Depends() # <<< USE THIS
) -> Any:
    """
    Authenticate user using OAuth2 password flow and return an access token.
    Receives username and password as form data.
    """
    player = crud.crud_player.get_player_by_username(db, username=form_data.username) # Use form_data.username
    if not player or not verify_password(form_data.password, player.hashed_password): # type: ignore # Use form_data.password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(player.id), expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@router.get("/me", response_model=schemas.Player) # Test endpoint
def read_users_me(
    current_player: models.Player = Depends(get_current_player) # Use the dependency
) -> Any:
    """
    Fetch the current logged in player.
    """
    return current_player

@router.post("/register", response_model=schemas.Player, status_code=status.HTTP_201_CREATED)
def register_new_user(
    *,
    db: Session = Depends(get_db),
    player_in: schemas.PlayerCreate
) -> Any:
    # ... (existing registration logic) ...
    existing_player = crud.crud_player.get_player_by_username(db, username=player_in.username)
    if existing_player:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A player with this username already exists.",
        )
    player = crud.crud_player.create_player(db, player_in=player_in)
    return player