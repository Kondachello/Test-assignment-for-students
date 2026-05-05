from enum import Enum
from typing import Any, NamedTuple

from pydantic import BaseModel, Field


class Intent(str, Enum):
    MAX_SPEED = "max_speed"
    BAD_QUALITY = "bad_quality"
    TWILIGHT_POSITION = "twilight_position"
    HARD_BRAKING = "hard_braking"
    M11_ROUTE = "m11_route"
    UNKNOWN = "unknown"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


class QueryResponse(BaseModel):
    status: str
    query: str
    intent: Intent
    result: dict[str, Any]


class IntentResponse(NamedTuple):
    intent: Intent
    rationale: str = ""
