from typing import Any

import polars as pl

from app.config import Settings
from app.data.loader import TelemetryStore
from app.handlers.base import register
from app.handlers.serialization import serialize_points
from app.schemas import Intent


@register(Intent.TWILIGHT_POSITION)
def twilight_position(store: TelemetryStore, settings: Settings) -> dict[str, Any]:
    twilight = store.frame.filter(
        pl.col("hour_msk").is_between(
            settings.twilight_start_hour,
            settings.twilight_end_hour,
            closed="left",
        )
    )
    points = serialize_points(
        twilight,
        columns=["datetime_msk", "latitude", "longitude", "height", "horizontal_speed"],
        aliases={"datetime_msk": "timestamp"},
        round_floats={"horizontal_speed": 3},
        limit=settings.response_max_points,
    )
    return {
        "window_msk": (
            f"{settings.twilight_start_hour:02d}:00-{settings.twilight_end_hour:02d}:00"
        ),
        "total_points": twilight.height,
        "returned": len(points),
        "points": points,
    }
