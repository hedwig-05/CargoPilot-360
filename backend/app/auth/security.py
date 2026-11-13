from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv

import jwt
from pwdlib import PasswordHash


# Password hashing
password_hash = PasswordHash.recommended()

load_dotenv()
# JWT configuration
SECRET_KEY = os.getenv("CARGOPILOT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "CARGOPILOT_SECRET_KEY environment variable is not configured."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def hash_password(password: str) -> str:
    """Convert a plain password into a secure hash."""
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """Verify a password against its stored hash."""
    return password_hash.verify(
        plain_password,
        hashed_password
    )


def create_access_token(user_id: int, role: str) -> str:
    """Generate a JWT access token."""

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expires_at
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""

    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )