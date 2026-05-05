import pytest

from app.llm.client import LLMError, parse_intent
from app.llm.prompts import render_system_prompt
from app.schemas import Intent


def test_parse_intent_pure_json() -> None:
    raw = '{"intent": "max_speed", "rationale": "asks about top speed"}'
    parsed = parse_intent(raw)
    assert parsed.intent is Intent.MAX_SPEED
    assert "top speed" in parsed.rationale


def test_parse_intent_extracts_from_chatter() -> None:
    raw = "Sure! Here is the JSON:\n```json\n{\"intent\": \"hard_braking\", \"rationale\": \"x\"}\n```"
    parsed = parse_intent(raw)
    assert parsed.intent is Intent.HARD_BRAKING


def test_parse_intent_unknown_label_falls_back() -> None:
    raw = '{"intent": "fly_to_mars", "rationale": "lol"}'
    parsed = parse_intent(raw)
    assert parsed.intent is Intent.UNKNOWN


def test_parse_intent_invalid_json_raises() -> None:
    with pytest.raises(LLMError):
        parse_intent("not json at all")


def test_parse_intent_rejects_non_object_json() -> None:
    with pytest.raises(LLMError):
        parse_intent('["max_speed"]')


def test_parse_intent_tolerates_control_chars_in_strings() -> None:
    raw = '{"intent": "hard_braking", "rationale": "with\nnewline\tand tab"}'
    parsed = parse_intent(raw)
    assert parsed.intent is Intent.HARD_BRAKING


def test_system_prompt_lists_every_intent() -> None:
    rendered = render_system_prompt()
    for intent in Intent:
        assert intent.value in rendered
