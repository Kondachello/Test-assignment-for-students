import math

import polars as pl

from app.data.loader import TelemetryStore, enrich


def test_enrich_adds_derived_columns(synthetic_frame: pl.DataFrame) -> None:
    expected = {
        "horizontal_speed",
        "speed_kmh",
        "acceleration",
        "datetime_msk",
        "hour_msk",
        "timestamp_s",
    }
    assert expected.issubset(set(synthetic_frame.columns))


def test_horizontal_speed_matches_pythagoras() -> None:
    raw = pl.DataFrame(
        {
            "_timestamp": [1_700_000_000_000_000_000, 1_700_000_001_000_000_000],
            "north_velocity": [3.0, 0.0],
            "east_velocity": [4.0, 0.0],
        }
    )
    enriched = enrich(raw, moscow_offset_hours=3)
    speeds = enriched["horizontal_speed"].to_list()
    assert math.isclose(speeds[0], 5.0)
    assert math.isclose(speeds[1], 0.0)


def test_acceleration_first_value_is_zero(synthetic_frame: pl.DataFrame) -> None:
    assert synthetic_frame["acceleration"][0] == 0.0


def test_hour_msk_uses_offset() -> None:
    raw = pl.DataFrame(
        {
            "_timestamp": [1_700_000_000_000_000_000],
            "north_velocity": [0.0],
            "east_velocity": [0.0],
        }
    )
    frame = enrich(raw, moscow_offset_hours=3)
    assert frame["hour_msk"][0] == 1


def test_store_loads_real_csv(real_data_path) -> None:
    if not real_data_path.exists():
        return
    store = TelemetryStore.from_csv(real_data_path, moscow_offset_hours=3)
    assert "datetime_msk" in store.frame.columns
    assert store.frame.height > 0
    assert "horizontal_speed" in store.frame.columns
