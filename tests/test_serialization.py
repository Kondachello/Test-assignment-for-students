from datetime import datetime

import polars as pl

from app.handlers.serialization import format_datetime, serialize_points


def test_format_datetime_handles_none_and_naive() -> None:
    assert format_datetime(None) is None
    assert format_datetime(datetime(2023, 11, 15, 16, 0, 0)) == "2023-11-15 16:00:00"


def test_serialize_points_renames_and_rounds() -> None:
    frame = pl.DataFrame(
        {
            "datetime_msk": [datetime(2023, 11, 15, 16, 0, 0)],
            "latitude": [55.5],
            "horizontal_speed": [12.345678],
            "status": [19],
        }
    )
    points = serialize_points(
        frame,
        columns=["datetime_msk", "latitude", "horizontal_speed", "status"],
        aliases={"datetime_msk": "timestamp"},
        round_floats={"horizontal_speed": 2},
    )
    assert points == [
        {
            "timestamp": "2023-11-15 16:00:00",
            "latitude": 55.5,
            "horizontal_speed": 12.35,
            "status": 19,
        }
    ]


def test_serialize_points_respects_limit() -> None:
    frame = pl.DataFrame({"a": list(range(10))})
    assert len(serialize_points(frame, columns=["a"], limit=3)) == 3
    assert len(serialize_points(frame, columns=["a"], limit=None)) == 10
