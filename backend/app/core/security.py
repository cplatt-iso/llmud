# backend/app/core/security.py
from datetime import datetime, timedelta, timezone # Use timezone-aware datetimes
from typing import Optional, Any, Union
from jose import JWTError, jwt # Import from jose
from passlib.context import CryptContext

from ..core.config import settings # Import our settings instance

# Initialize CryptContext. We'll use bcrypt.
# "auto" will use the first scheme (bcrypt) for hashing new passwords
# and will also be able to verify passwords hashed with any scheme listed.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)} # "sub" is the standard claim for subject (e.g., player_id)
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt