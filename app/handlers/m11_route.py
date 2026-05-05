from typing import Any

import polars as pl

from app.config import Settings
from app.data.loader import TelemetryStore
from app.handlers.base import register
from app.handlers.serialization import format_datetime, serialize_points
from app.schemas import Intent


@register(Intent.M11_ROUTE)
def m11_route(store: TelemetryStore, settings: Settings) -> dict[str, Any]:
    bbox = settings.m11_bbox()
    on_route = store.frame.filter(
        pl.col("latitude").is_between(bbox["lat_min"], bbox["lat_max"])
        & pl.col("longitude").is_between(bbox["lon_min"], bbox["lon_max"])
    )
    points = serialize_points(
        on_route,
        columns=["datetime_msk", "latitude", "longitude", "horizontal_speed"],
        aliases={"datetime_msk": "timestamp"},
        round_floats={"horizontal_speed": 3},
        limit=settings.response_max_points,
    )
    first_seen = last_seen = None
    if on_route.height:
        first_seen = format_datetime(on_route.row(0, named=True)["datetime_msk"])
        last_seen = format_datetime(on_route.row(-1, named=True)["datetime_msk"])

    return {
        "total_points": on_route.height,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "bounding_box": bbox,
        "returned": len(points),
        "points": points,
    }
