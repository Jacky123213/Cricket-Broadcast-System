from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from .app_paths import RESOURCE_ROOT, default_data_root


PROJECT_ROOT = RESOURCE_ROOT


class Settings(BaseSettings):
    app_name: str = "Cricket Broadcast System"
    host: str = "0.0.0.0"
    port: int = 8765
    data_root: Path = Field(default_factory=default_data_root)
    database_path: Path | None = None
    scoreboard_path: Path | None = None
    certificate_dir: Path | None = None
    device_timeout_seconds: int = 12
    heartbeat_interval_seconds: int = 4
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None

    @model_validator(mode="after")
    def resolve_paths(self):
        self.data_root = self.data_root.resolve()
        self.database_path = self.database_path or self.data_root / "storage" / "backyard_drs.db"
        self.scoreboard_path = self.scoreboard_path or self.data_root / "data"
        self.certificate_dir = self.certificate_dir or self.data_root / "certs"
        # An explicitly supplied None retains the existing no-TLS test/config option.
        if "ssl_certfile" not in self.model_fields_set:
            self.ssl_certfile = self.certificate_dir / "server.crt"
        if "ssl_keyfile" not in self.model_fields_set:
            self.ssl_keyfile = self.certificate_dir / "server.key.pem"
        return self

    model_config = SettingsConfigDict(
        env_prefix="DRS_",
        env_file=default_data_root() / ".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
