from app.handlers.base import HANDLERS, dispatch, register

from app.handlers import (
    bad_quality,
    hard_braking,
    m11_route,
    max_speed,
    twilight_position,
)

__all__ = ["HANDLERS", "dispatch", "register"]
