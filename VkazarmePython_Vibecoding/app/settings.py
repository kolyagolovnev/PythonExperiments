from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret: str = "change_this_to_a_strong_random_secret"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    password_hash_rounds: int = 12
    media_max_bytes: int = 5_000_000
    admins_file: Path = Path("admins.json")
    # Example data seeded at startup (idempotent). Disable in production with
    # SEED_ENABLED=false.
    seed_enabled: bool = True
    account_examples_dir: Path = Path("account_examples")
    group_examples_dir: Path = Path("group_examples")
    # Empty (default) -> in-memory repositories; e.g.
    # postgresql+asyncpg://vkazarme:vkazarme@localhost:5433/vkazarme -> database
    database_url: str = ""
