# app/config.py
# Centralized configuration — reads .env and exposes typed settings to the app

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    All app configuration lives here.
    Pydantic reads values from environment variables automatically.
    Type annotations enforce validation — wrong types raise errors at startup.
    """

    # --- Database ---
    database_url: str

    # --- Supabase ---
    supabase_url: str
    supabase_key: str

    # --- Auth ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"           # Default value — can be overridden in .env
    access_token_expire_minutes: int = 30

    # --- AI ---
    gemini_api_key: str

    # --- Cache & Tasks ---
    redis_url: str

    # --- Notifications ---
    africas_talking_key: str
    africas_talking_user: str
    resend_api_key: str

    # --- App ---
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        """Helper to check environment — used to toggle debug features."""
        return self.environment == "production"

    @property
    def origins_list(self) -> list[str]:
        """Converts the comma-separated string into a list for CORS config."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    class Config:
        # Tells Pydantic where to find the .env file
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Makes matching case-insensitive: DATABASE_URL matches database_url
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    @lru_cache() means this function runs ONCE — the first call reads .env,
    all subsequent calls return the same object from memory.
    No need to re-read the file on every request.
    """
    return Settings()


# Shortcut — import this directly in other modules
settings = get_settings()