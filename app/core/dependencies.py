# app/core/dependencies.py
# FastAPI dependencies — reusable functions injected into routes

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# HTTPBearer extracts the token from the Authorization header
# Format: "Authorization: Bearer eyJhbGc..."
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that protects routes — extracts and validates the JWT.

    Usage in any protected route:
        @router.get("/me")
        def get_me(current_user: User = Depends(get_current_user)):
            return current_user

    If the token is missing, invalid, or expired → 401 Unauthorized.
    If valid → returns the User object from DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode the token
    token = credentials.credentials
    user_id = decode_access_token(token)

    if not user_id:
        raise credentials_exception

    # Fetch user from DB
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user