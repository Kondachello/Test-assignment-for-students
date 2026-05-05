import logging
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)

NS_PER_S = 1_000_000_000


class TelemetryStore:
    """In-memory telemetry dataset enriched with derived metrics.

    Loaded once at startup; immutable afterwards. Polars expressions on
    the cached frame are vectorised and cheap relative to repeated I/O.
    """

    def __init__(self, frame: pl.DataFrame) -> None:
        self.frame = frame

    @classmethod
    def from_csv(cls, path: Path, *, moscow_offset_hours: int) -> "TelemetryStore":
        if not path.exists():
            raise FileNotFoundError(f"Telemetry file not found: {path}")

        logger.info("Loading telemetry from %s", path)
        raw = pl.read_csv(path, infer_schema_length=2000)
        frame = enrich(raw, moscow_offset_hours=moscow_offset_hours)
        logger.info("Telemetry loaded: %d rows × %d cols", frame.height, frame.width)
        return cls(frame)


def enrich(frame: pl.DataFrame, *, moscow_offset_hours: int) -> pl.DataFrame:
    """Attach derived columns required by the handlers.

    horizontal_speed (m/s)   — sqrt(vN² + vE²)
    speed_kmh                — horizontal_speed * 3.6
    acceleration (m/s²)      — dv / dt over consecutive samples
    timestamp_s              — timestamp in seconds (float)
    datetime_msk             — naive datetime in Moscow time
    hour_msk                 — hour-of-day in Moscow time
    """
    if "_timestamp" not in frame.columns:
        raise ValueError("Column '_timestamp' is required")

    return (
        frame.sort("_timestamp")
        .with_columns(
            (pl.col("_timestamp").cast(pl.Float64) / NS_PER_S).alias("timestamp_s"),
            (pl.col("north_velocity") ** 2 + pl.col("east_velocity") ** 2)
            .sqrt()
            .alias("horizontal_speed"),
        )
        .with_columns(
            (pl.col("horizontal_speed") * 3.6).alias("speed_kmh"),
            (
                pl.from_epoch("timestamp_s", time_unit="s")
                + pl.duration(hours=moscow_offset_hours)
            ).alias("datetime_msk"),
            (pl.col("horizontal_speed").diff() / pl.col("timestamp_s").diff())
            .fill_null(0.0)
            .alias("acceleration"),
        )
        .with_columns(pl.col("datetime_msk").dt.hour().alias("hour_msk"))
    )
