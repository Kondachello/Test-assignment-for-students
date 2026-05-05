from typing import Any, Callable

from app.config import Settings
from app.data.loader import TelemetryStore
from app.schemas import Intent

QueryHandler = Callable[[TelemetryStore, Settings], dict[str, Any]]

HANDLERS: dict[Intent, QueryHandler] = {}


def register(intent: Intent) -> Callable[[QueryHandler], QueryHandler]:
    """Decorator: bind ``handler`` to ``intent`` in the registry."""

    def decorator(handler: QueryHandler) -> QueryHandler:
        HANDLERS[intent] = handler
        return handler

    return decorator


def dispatch(
    intent: Intent,
    store: TelemetryStore,
    settings: Settings,
) -> dict[str, Any]:
    """Run the handler bound to ``intent`` and return its payload."""
    handler = HANDLERS.get(intent)
    if handler is None:
        return {
            "message": (
                "Запрос не удалось классифицировать ни в один из поддерживаемых "
                "сценариев. Попробуйте переформулировать."
            ),
            "supported_intents": [i.value for i in Intent if i is not Intent.UNKNOWN],
        }
    return handler(store, settings)
