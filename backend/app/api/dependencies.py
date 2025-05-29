# backend/app/api/dependencies.py
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # Handles extracting token from "Authorization: Bearer <token>"
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import uuid # For converting subject string back to UUID

from app.core.config import settings
from app import models, schemas, crud # models.Player, schemas.Player (for return type)
from app.db.session import get_db # To get DB session

# This tells FastAPI that token URL is /api/v1/users/login
# It's used by Swagger UI to know how to get a token for testing protected endpoints.
# The path should match your actual login endpoint path *relative to the app root*.
# Our login is /api/v1/users/login.
# If your main app includes v1_api_router with prefix /api/v1,
# and user_router is included in v1_api_router with prefix /users,
# and login endpoint is /login, then the full path is /api/v1/users/login.
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/users/login" #  e.g. "/api/v1/users/login"
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
        username_or_player_id: Optional[str] = payload.get("sub") # We stored player_id as "sub"
        if username_or_player_id is None:
            raise credentials_exception
        
        # Assuming "sub" contains the player_id as a UUID string
        try:
            player_uuid = uuid.UUID(username_or_player_id)
        except ValueError:
            print(f"Error: Subject '{username_or_player_id}' in token is not a valid UUID.")
            raise credentials_exception
            
        # token_data = schemas.TokenPayload(id=username_or_player_id) # If you have a TokenPayload schema
    except JWTError as e:
        print(f"JWTError during token decode: {e}") # Log the error
        raise credentials_exception
    
    player = crud.crud_player.get_player(db, player_id=player_uuid) # Fetch player by UUID
    if player is None:
        raise credentials_exception
    return player

# Optional: A dependency for current active superuser (not needed yet)
# def get_current_active_superuser(current_user: models.User = Depends(get_current_user)):
#     if not crud.user.is_superuser(current_user):
#         raise HTTPException(status_code=403_FORBIDDEN, detail="The user doesn't have enough privileges")
#     return current_user