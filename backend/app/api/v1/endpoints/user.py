# backend/app/api/v1/endpoints/user.py
from fastapi import APIRouter, Depends, HTTPException, status, Body, Form, Request # Added Body
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
import logging

logger = logging.getLogger(__name__)
router = APIRouter() 

class UserLoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.get("/debug-headers")
def debug_headers(request: Request):
    """
    A simple, unprotected endpoint to dump all received headers to the log.
    """
    header_log_message = "\n" + "="*50 + "\nHEADERS RECEIVED AT /debug-headers:\n"
    for name, value in request.headers.items():
        header_log_message += f"  {name}: {value}\n"
    header_log_message += "="*50
    logger.info(header_log_message) # Using INFO to make sure it prints
    
    return {"message": "Headers logged to backend console."}

@router.post("/login", response_model=Token)
def login_user_for_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends() 
) -> Any:
    try:
        player = crud.crud_player.get_player_by_username(db, username=form_data.username) 
        if not player or not verify_password(form_data.password, player.hashed_password): # type: ignore 
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
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error during login.")

@router.get("/me", response_model=schemas.Player) 
def read_users_me(
    current_player: models.Player = Depends(get_current_player) 
) -> Any:
    return current_player

@router.post("/register", response_model=schemas.Player, status_code=status.HTTP_201_CREATED)
def register_new_user(
    *,
    db: Session = Depends(get_db),
    player_in: schemas.PlayerCreate
) -> Any:
    try:
        existing_player = crud.crud_player.get_player_by_username(db, username=player_in.username)
        if existing_player:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A player with this username already exists.",
            )
        player = crud.crud_player.create_player(db, player_in=player_in)
        return player
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error during registration.")