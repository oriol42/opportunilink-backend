# app/routes/auth.py
# Authentication routes — register and login

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token

# APIRouter groups related routes together
# prefix and tags are applied to all routes in this router
router = APIRouter()


# ================================
# REGISTER
# ================================

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Creates a new user account.

    Flow:
    1. Check if email already exists
    2. Hash the password
    3. Create the user in DB
    4. Generate a JWT token
    5. Return token + user data
    """

    # Step 1 — Check for duplicate email
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    # Step 2 — Hash the password
    # We NEVER store plain text passwords
    hashed = hash_password(user_data.password)

    # Step 3 — Create the user object and save to DB
    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed,
    )
    db.add(new_user)
    db.flush()  # Sends the INSERT to DB but doesn't commit yet
                # This gives us the generated UUID before commit

    # Step 4 — Generate JWT token
    token = create_access_token(str(new_user.id))

    # Step 5 — Commit and return
    db.commit()
    db.refresh(new_user)  # Reloads the object with all DB-generated values

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(new_user),
    )


# ================================
# LOGIN
# ================================

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user and returns a JWT token.

    Flow:
    1. Find user by email
    2. Verify password against stored hash
    3. Generate a new JWT token
    4. Return token + user data

    Security note: we return the same error for "email not found"
    and "wrong password" — this prevents email enumeration attacks.
    """

    # Steps 1 & 2 — Find user and verify password
    user = db.query(User).filter(User.email == credentials.email).first()

    # Same error message whether email doesn't exist OR password is wrong
    # This prevents attackers from knowing which emails are registered
    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    if not user:
        raise invalid_credentials_error

    if not verify_password(credentials.password, user.hashed_password):
        raise invalid_credentials_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Step 3 — Generate token
    token = create_access_token(str(user.id))

    # Step 4 — Return
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ================================
# ME — test protected route
# ================================

@router.get("/me", response_model=UserResponse)
def get_me(db: Session = Depends(get_db)):
    """Temporary route to test auth — will be moved to users.py later."""
    from app.core.dependencies import get_current_user
    from fastapi import Depends as D
    # We'll wire this properly in the next step
    pass