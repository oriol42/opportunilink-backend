# app/core/security.py
# Password hashing and JWT token management

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

# ================================
# PASSWORD HASHING
# ================================

# CryptContext manages the hashing algorithm
# bcrypt is the industry standard — slow by design to resist brute force
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Converts a plain text password into a bcrypt hash.
    Example: "mypassword" → "$2b$12$KIXabc..."
    The hash is different every time even for the same password (salt).
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks if a plain password matches a stored hash.
    We never "decrypt" — we re-hash and compare.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ================================
# JWT TOKENS
# ================================

def create_access_token(user_id: str) -> str:
    """
    Creates a signed JWT token containing the user's ID.

    Structure of a JWT:
    - Header: algorithm used (HS256)
    - Payload: data we store (sub = user_id, exp = expiry)
    - Signature: proves the token wasn't tampered with

    Anyone can READ a JWT — but only we can CREATE a valid one
    because only we have the JWT_SECRET.
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),   # Subject — who this token belongs to
        "exp": expire,          # Expiry — token is invalid after this
        "iat": datetime.utcnow(), # Issued at — when the token was created
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> Optional[str]:
    """
    Decodes and validates a JWT token.
    Returns the user_id if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        return user_id if user_id else None
    except JWTError:
        return None