from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.limiter import limiter

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, user_data: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    hashed = hash_password(user_data.password)
    new_user = User(email=user_data.email, full_name=user_data.full_name, hashed_password=hashed)
    db.add(new_user)
    db.flush()
    token = create_access_token(str(new_user.id))
    db.commit()
    db.refresh(new_user)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(new_user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    invalid = HTTPException(status_code=401, detail="Invalid email or password")

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise invalid
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Change le mot de passe de l'utilisateur connecté.
    Nécessite le mot de passe actuel pour confirmer l'identité.
    """
    from app.core.dependencies import get_current_user
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from app.core.security import decode_access_token

    # Extraire le token manuellement (pas de Depends ici à cause du limiter)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Vérifier le mot de passe actuel
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Mot de passe actuel incorrect"
        )

    # Valider le nouveau mot de passe
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Le nouveau mot de passe doit faire au moins 8 caractères"
        )

    # Appliquer le nouveau mot de passe
    user.hashed_password = hash_password(data.new_password)
    db.commit()

    return {"message": "Mot de passe modifié avec succès"}


@router.get("/me", response_model=UserResponse)
def get_me():
    pass
