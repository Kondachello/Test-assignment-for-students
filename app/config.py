from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-oss-20b:free"
    openrouter_timeout: float = 30.0
    openrouter_max_retries: int = 3

    data_path: Path = Path("data/data.csv")

    moscow_offset_hours: int = 3
    twilight_start_hour: int = 16
    twilight_end_hour: int = 19
    bad_quality_pos_type: int = 19
    hard_braking_threshold: float = -2.0
    m11_lat_min: float = 55.5
    m11_lat_max: float = 60.0
    m11_lon_min: float = 30.0
    m11_lon_max: float = 37.5

    response_max_points: int = 100
    log_level: str = "INFO"

    def m11_bbox(self) -> dict[str, float]:
        return {
            "lat_min": self.m11_lat_min,
            "lat_max": self.m11_lat_max,
            "lon_min": self.m11_lon_min,
            "lon_max": self.m11_lon_max,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
