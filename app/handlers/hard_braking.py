from typing import Any

import polars as pl

from app.config import Settings
from app.data.loader import TelemetryStore
from app.handlers.base import register
from app.handlers.serialization import format_datetime
from app.schemas import Intent


@register(Intent.HARD_BRAKING)
def hard_braking(store: TelemetryStore, settings: Settings) -> dict[str, Any]:
    """Detect hard-braking events.

    Consecutive samples with ``acceleration < threshold`` are fused into a
    single event. Each event reports its peak deceleration (and the location
    at that peak) plus the speed bracketing the event — i.e. the sample just
    before the event began and the sample just after it ended.
    """
    threshold = settings.hard_braking_threshold
    frame = store.frame

    marked = (
        frame.with_row_index("__idx")
        .with_columns((pl.col("acceleration") < threshold).alias("__is_brake"))
        .with_columns(
            (pl.col("__is_brake").cast(pl.Int8).diff().fill_null(1) != 0)
            .cum_sum()
            .alias("__group")
        )
    )
    events_frame = marked.filter(pl.col("__is_brake"))
    if events_frame.is_empty():
        return {
            "total_braking_events": 0,
            "max_deceleration": None,
            "avg_deceleration": None,
            "threshold_ms2": threshold,
            "events": [],
        }

    per_event = (
        events_frame.group_by("__group", maintain_order=True)
        .agg(
            pl.col("acceleration").min().alias("deceleration"),
            pl.col("__idx").min().alias("idx_start"),
            pl.col("__idx").max().alias("idx_end"),
            pl.col("datetime_msk").sort_by("acceleration").first().alias("ts_peak"),
            pl.col("latitude").sort_by("acceleration").first().alias("lat_peak"),
            pl.col("longitude").sort_by("acceleration").first().alias("lon_peak"),
        )
        .sort("deceleration")
    )

    speed_kmh = frame["speed_kmh"].to_list()
    last_idx = frame.height - 1
    events = [
        {
            "timestamp": format_datetime(ev["ts_peak"]),
            "latitude": float(ev["lat_peak"]),
            "longitude": float(ev["lon_peak"]),
            "deceleration": round(float(ev["deceleration"]), 3),
            "speed_before": round(speed_kmh[max(0, ev["idx_start"] - 1)], 2),
            "speed_after": round(speed_kmh[min(last_idx, ev["idx_end"] + 1)], 2),
        }
        for ev in per_event.iter_rows(named=True)
    ][: settings.response_max_points]

    return {
        "total_braking_events": per_event.height,
        "max_deceleration": round(float(per_event["deceleration"].min()), 3),
        "avg_deceleration": round(float(per_event["deceleration"].mean()), 3),
        "threshold_ms2": threshold,
        "events": events,
    }
