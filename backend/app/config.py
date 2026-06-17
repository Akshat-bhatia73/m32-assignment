"""Application configuration via pydantic-settings (reads from env / .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql+psycopg://user:password@localhost/m32"

    # Auth
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # LLM
    llm_provider: str = "gemini"  # "gemini" | "openai"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # Composio
    composio_api_key: str = ""
    composio_timezone: str = "UTC"  # IANA tz for created calendar events

    # CORS / cookies
    frontend_origin: str = "http://localhost:5173"
    cookie_samesite: str = "lax"  # "lax" (dev) | "none" (cross-site prod)
    cookie_secure: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
