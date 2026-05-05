import json
import logging
import re
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings
from app.llm.prompts import render_system_prompt
from app.schemas import Intent, IntentResponse

logger = logging.getLogger(__name__)

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(RuntimeError):
    """Raised when the LLM call cannot be completed or parsed."""


class OpenRouterClient:
    """Thin async wrapper around OpenRouter's chat-completions endpoint."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=settings.openrouter_timeout)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(self, messages: list[dict[str, str]]) -> str:
        if not self._settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not configured")

        url = f"{self._settings.openrouter_base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._settings.openrouter_model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/itmo-ct/semantic-search",
            "X-Title": "Telemetry Semantic Search",
        }

        body = await self._post_with_retry(url, payload, headers)
        return _extract_content(body)

    async def _post_with_retry(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._settings.openrouter_max_retries),
                wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
                retry=retry_if_exception_type(
                    (httpx.TransportError, httpx.HTTPStatusError)
                ),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.post(url, json=payload, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        response.raise_for_status()
                    if response.status_code >= 400:
                        raise LLMError(
                            f"OpenRouter responded {response.status_code}: "
                            f"{response.text[:200]}"
                        )
                    return response.json()
        except RetryError as exc:
            raise LLMError("Retries exhausted while calling OpenRouter") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"HTTP error talking to OpenRouter: {exc}") from exc

        raise LLMError("Unreachable: retry loop produced no response")


def _extract_content(body: dict[str, Any]) -> str:
    """Pull the assistant text out of an OpenAI-shaped chat response.

    Some reasoning models (e.g. ``openai/gpt-oss-*``) leave ``content``
    empty and put the text into ``reasoning`` — we fall back to that.
    """
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Malformed OpenRouter response: {body!r}") from exc

    content = message.get("content") or message.get("reasoning") or ""
    if not isinstance(content, str) or not content.strip():
        raise LLMError(f"Empty LLM response: {message!r}")
    return content


def parse_intent(raw: str) -> IntentResponse:
    """Parse LLM output into an :class:`IntentResponse`.

    Free-tier models occasionally wrap JSON in markdown fences or prepend
    chatter; the regex below extracts the first balanced object so we are
    resilient to that.
    """
    payload = _load_json_object(raw)

    label = str(payload.get("intent", "")).strip().lower()
    try:
        intent = Intent(label)
    except ValueError:
        logger.warning("Unknown intent label from LLM: %r", label)
        intent = Intent.UNKNOWN

    rationale = str(payload.get("rationale", ""))[:200]
    return IntentResponse(intent=intent, rationale=rationale)


def _load_json_object(raw: str) -> dict[str, Any]:
    candidates = [raw]
    match = _JSON_OBJECT.search(raw)
    if match is not None and match.group(0) != raw:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    raise LLMError(f"LLM did not return a JSON object: {raw!r}")


async def classify_intent(client: OpenRouterClient, query: str) -> IntentResponse:
    messages = [
        {"role": "system", "content": render_system_prompt()},
        {"role": "user", "content": query},
    ]
    raw = await client.chat(messages)
    return parse_intent(raw)
