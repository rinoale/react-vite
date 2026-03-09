import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=f".env.{os.getenv('APP_ENV', 'development')}",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Environment ---
    app_env: str = "development"

    # --- Database ---
    database_url: str = ""
    db_user: str = "mabinogi"
    db_password: str = "mabinogi"
    db_host: str = "localhost"
    db_port: str = "5432"
    db_name: str = "mabinogi"

    # --- Auth ---
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Discord OAuth ---
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "https://dev.mabitra.local/api/auth/discord/callback"

    # --- Frontend ---
    frontend_url: str = "https://dev.mabitra.local"

    # --- Nexon Open API ---
    mabinogi_open_api_url: str = ""
    mabinogi_open_api_key: str = ""

    # --- Cookie ---
    cookie_domain: str = ".mabitra.local"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # --- CORS ---
    cors_origins: list[str] = [
        "https://dev.mabitra.local",
    ]

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
