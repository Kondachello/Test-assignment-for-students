from pathlib import Path

import polars as pl
import pytest

from app.config import Settings
from app.data.loader import TelemetryStore, enrich

NS = 1_000_000_000

BASE_UTC = 1_700_006_400


def _at_msk_hour(hour: int, second_offset: int = 0) -> int:
    """Return a nanosecond timestamp landing at ``hour:00`` Moscow time."""
    return (BASE_UTC + (hour - 3) * 3600 + second_offset) * NS


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(openrouter_api_key="test-key")


@pytest.fixture
def synthetic_frame() -> pl.DataFrame:
    """Hand-crafted dataset covering every handler scenario."""
    rows: list[dict[str, object]] = []

    for i in range(5):
        rows.append(
            {
                "_timestamp": _at_msk_hour(16, i),
                "latitude": 56.0 + i * 0.01,
                "longitude": 35.0 + i * 0.01,
                "height": 100.0,
                "north_velocity": 20.0,
                "east_velocity": 0.0,
                "pos_type__type": 56,
            }
        )

    for i in range(3):
        rows.append(
            {
                "_timestamp": _at_msk_hour(12, i),
                "latitude": 50.0,
                "longitude": 50.0,
                "height": 0.0,
                "north_velocity": 5.0,
                "east_velocity": 0.0,
                "pos_type__type": 19,
            }
        )

    speeds = [30.0, 25.0, 18.0, 8.0, 2.0]
    for i, v in enumerate(speeds):
        rows.append(
            {
                "_timestamp": _at_msk_hour(10, i),
                "latitude": 45.0,
                "longitude": 60.0,
                "height": 0.0,
                "north_velocity": v,
                "east_velocity": 0.0,
                "pos_type__type": 56,
            }
        )

    rows.append(
        {
            "_timestamp": _at_msk_hour(9),
            "latitude": 56.5,
            "longitude": 36.0,
            "height": 0.0,
            "north_velocity": 30.0,
            "east_velocity": 40.0,
            "pos_type__type": 56,
        }
    )

    raw = pl.DataFrame(rows)
    return enrich(raw, moscow_offset_hours=3)


@pytest.fixture
def store(synthetic_frame: pl.DataFrame) -> TelemetryStore:
    return TelemetryStore(synthetic_frame)


@pytest.fixture
def real_data_path() -> Path:
    return Path(__file__).parent.parent / "data" / "data.csv"
