# backend/app/core/security.py
from datetime import datetime, timedelta, timezone  # Use timezone-aware datetimes
from typing import Any, Optional, Union

from jose import JWTError, jwt  # Import from jose
from passlib.context import CryptContext

from ..core.config import settings  # Import our settings instance

# Initialize CryptContext. We'll use bcrypt.
# "auto" will use the first scheme (bcrypt) for hashing new passwords
# and will also be able to verify passwords hashed with any scheme listed.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.
    
    Bcrypt has a 72-byte limit. We truncate to ensure compatibility.
    """
    # Truncate password to 72 bytes if needed (bcrypt limitation)
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Decode back to string, ignoring any incomplete UTF-8 sequences at the boundary
    plain_password = password_bytes.decode('utf-8', errors='ignore')
    
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError as e:
        # Handle bcrypt errors gracefully
        if "password cannot be longer than 72 bytes" in str(e):
            # Try with character truncation as last resort
            plain_password = plain_password[:72]
            try:
                return pwd_context.verify(plain_password, hashed_password)
            except Exception:
                return False
        raise


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.
    
    Bcrypt has a 72-byte limit. We truncate to ensure compatibility.
    """
    # Truncate password to 72 bytes if needed (bcrypt limitation)
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Decode back to string, ignoring any incomplete UTF-8 sequences at the boundary
    password = password_bytes.decode('utf-8', errors='ignore')
    
    try:
        return pwd_context.hash(password)
    except ValueError as e:
        # If we still hit the 72-byte limit, try one more time with strict truncation
        if "password cannot be longer than 72 bytes" in str(e):
            password = password[:72]
            return pwd_context.hash(password)
        raise


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
    }  # "sub" is the standard claim for subject (e.g., player_id)
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
