from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # --- Database ---
    database_url: str
    # --- Supabase ---
    supabase_url: str
    supabase_key: str
    # --- Auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    # --- AI (optionnel pour le MVP) ---
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    # --- Cache & Tasks (optionnel pour le MVP) ---
    redis_url: str | None = None
    # --- Notifications (optionnel pour le MVP) ---
    africas_talking_key: str | None = None
    africas_talking_user: str | None = None
    resend_api_key: str | None = None
    # --- App ---
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
