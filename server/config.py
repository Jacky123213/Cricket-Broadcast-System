from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "Backyard Cricket Studio"
    host: str = "0.0.0.0"
    port: int = 8765
    database_path: Path = PROJECT_ROOT / "storage" / "backyard_drs.db"
    device_timeout_seconds: int = 12
    heartbeat_interval_seconds: int = 4
    ssl_certfile: Path | None = PROJECT_ROOT / "certs" / "server.crt"
    ssl_keyfile: Path | None = PROJECT_ROOT / "certs" / "server.key.pem"

    model_config = SettingsConfigDict(
        env_prefix="DRS_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
