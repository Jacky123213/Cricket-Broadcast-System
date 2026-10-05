from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class CameraRole(StrEnum):
    UMPIRE_POV = "UMPIRE_POV"
    CREASE_LEFT = "CREASE_LEFT"
    CREASE_RIGHT = "CREASE_RIGHT"
    WICKET_MIC = "WICKET_MIC"
    OTHER = "OTHER"


class BatteryStatus(BaseModel):
    level: int = Field(strict=True, ge=0, le=100)
    charging: bool = Field(strict=True)


class DeviceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=48)
    role: CameraRole

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()
