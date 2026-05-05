from typing import Any

import polars as pl

from app.config import Settings
from app.data.loader import TelemetryStore
from app.handlers.base import register
from app.handlers.serialization import serialize_points
from app.schemas import Intent


@register(Intent.BAD_QUALITY)
def bad_quality(store: TelemetryStore, settings: Settings) -> dict[str, Any]:
    bad = store.frame.filter(pl.col("pos_type__type") == settings.bad_quality_pos_type)
    total = store.frame.height
    percentage = round(bad.height / total * 100.0, 2) if total else 0.0

    points = serialize_points(
        bad,
        columns=["datetime_msk", "latitude", "longitude", "pos_type__type", "horizontal_speed"],
        aliases={"datetime_msk": "timestamp", "pos_type__type": "status"},
        round_floats={"horizontal_speed": 3},
        limit=settings.response_max_points,
    )
    return {
        "total_points": bad.height,
        "percentage_of_trip": percentage,
        "returned": len(points),
        "points": points,
    }
