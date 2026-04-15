# app/schemas/__init__.py

from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserProfileUpdate,
    UserResponse,
    TokenResponse,
)
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityFeedItem,
)
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
)