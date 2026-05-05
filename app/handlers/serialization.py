from datetime import datetime
from typing import Any, Mapping

import polars as pl

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_datetime(value: datetime | None) -> str | None:
    """Render a naive ``datetime`` as ``YYYY-MM-DD HH:MM:SS`` for JSON output."""
    return value.strftime(DATETIME_FORMAT) if value is not None else None


def serialize_points(
    frame: pl.DataFrame,
    *,
    columns: list[str],
    aliases: Mapping[str, str] | None = None,
    round_floats: Mapping[str, int] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Serialise the head of ``frame`` into a list of JSON-friendly dicts.

    ``columns`` selects what to project. ``aliases`` renames keys, e.g.
    ``{"datetime_msk": "timestamp"}``. ``round_floats`` rounds the named
    columns to the given precision. Datetime values are stringified.
    """
    aliases = aliases or {}
    rounding = round_floats or {}
    selected = frame.head(limit) if limit is not None else frame
    selected = selected.select(columns)

    points: list[dict[str, Any]] = []
    for row in selected.iter_rows(named=True):
        point: dict[str, Any] = {}
        for key, value in row.items():
            target = aliases.get(key, key)
            if isinstance(value, datetime):
                point[target] = format_datetime(value)
            elif value is not None and key in rounding:
                point[target] = round(float(value), rounding[key])
            else:
                point[target] = value
        points.append(point)
    return points
