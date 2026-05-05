import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.data.loader import TelemetryStore
from app.handlers import dispatch
from app.llm.client import LLMError, OpenRouterClient, classify_intent
from app.logging_config import setup_logging
from app.schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_level)

    if not settings.openrouter_api_key:
        logger.warning(
            "OPENROUTER_API_KEY is empty — /query will return 502 until it is set"
        )

    store = TelemetryStore.from_csv(
        settings.data_path,
        moscow_offset_hours=settings.moscow_offset_hours,
    )
    llm = OpenRouterClient(settings)

    app.state.settings = settings
    app.state.store = store
    app.state.llm = llm

    logger.info(
        "Service ready: %d rows loaded, model=%s",
        store.frame.height,
        settings.openrouter_model,
    )
    try:
        yield
    finally:
        await llm.aclose()


app = FastAPI(
    title="Telemetry Semantic Search",
    description=(
        "Natural-language search over NovAtel GNSS/INS telemetry powered "
        "by OpenRouter free-tier LLMs."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _store(request: Request) -> TelemetryStore:
    return request.app.state.store


def _llm(request: Request) -> OpenRouterClient:
    return request.app.state.llm


@app.get("/health", tags=["meta"])
async def health(
    settings: Settings = Depends(_settings),
    store: TelemetryStore = Depends(_store),
) -> dict[str, object]:
    return {
        "status": "ok",
        "rows": store.frame.height,
        "model": settings.openrouter_model,
    }


@app.post("/query", response_model=QueryResponse, tags=["search"])
async def query_endpoint(
    payload: QueryRequest,
    settings: Settings = Depends(_settings),
    store: TelemetryStore = Depends(_store),
    llm: OpenRouterClient = Depends(_llm),
) -> QueryResponse:
    try:
        intent_resp = await classify_intent(llm, payload.query)
    except LLMError as exc:
        logger.exception("Intent classification failed")
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    logger.info(
        "Query intent=%s rationale=%r",
        intent_resp.intent.value,
        intent_resp.rationale,
    )

    result = dispatch(intent_resp.intent, store, settings)
    if intent_resp.rationale:
        result.setdefault("_rationale", intent_resp.rationale)

    return QueryResponse(
        status="success",
        query=payload.query,
        intent=intent_resp.intent,
        result=result,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": "internal_error", "detail": str(exc)},
    )
