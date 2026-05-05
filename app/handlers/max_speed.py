from typing import Any

import polars as pl

from app.config import Settings
from app.data.loader import TelemetryStore
from app.handlers.base import register
from app.handlers.serialization import format_datetime
from app.schemas import Intent


@register(Intent.MAX_SPEED)
def max_speed(store: TelemetryStore, settings: Settings) -> dict[str, Any]:
    if store.frame.is_empty():
        return {"max_speed": None, "units": "km/h", "timestamp": None}

    idx = int(store.frame.select(pl.col("speed_kmh").arg_max()).item())
    row = store.frame.row(idx, named=True)
    return {
        "max_speed": round(float(row["speed_kmh"]), 2),
        "max_speed_ms": round(float(row["horizontal_speed"]), 3),
        "units": "km/h",
        "timestamp": format_datetime(row["datetime_msk"]),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
    }
