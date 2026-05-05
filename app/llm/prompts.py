from app.schemas import Intent

INTENT_DESCRIPTIONS: dict[Intent, str] = {
    Intent.MAX_SPEED: (
        "Aggregation over horizontal speed: maximum, top speed, peak velocity, "
        "fastest moment. Russian: 'максимальная скорость', 'максималка', 'top speed'."
    ),
    Intent.BAD_QUALITY: (
        "Filter samples where positioning quality is bad (pos_type__type == 19): "
        "GPS issues, weak fix, lost signal. Russian: 'плохое качество', "
        "'проблемы с GPS', 'плохая точность'."
    ),
    Intent.TWILIGHT_POSITION: (
        "Time slice between 16:00 and 19:00 Moscow time (twilight, dusk, evening). "
        "Russian: 'сумерки', 'вечером', 'на закате'."
    ),
    Intent.HARD_BRAKING: (
        "Detect hard braking events: deceleration < -2 m/s^2. "
        "Russian: 'резкое торможение', 'тормозил', 'резко тормозил'."
    ),
    Intent.M11_ROUTE: (
        "Geospatial filter for M11 motorway corridor in Russia "
        "(lat 55.5..60.0, lon 30.0..37.5). Russian: 'трасса М11', 'на М11'."
    ),
}


SYSTEM_PROMPT = """You are an intent classifier for a vehicle telemetry search engine.
You receive a natural-language question (English or Russian) about navigation data
recorded by a self-driving truck and you must select exactly ONE intent label
from the fixed list below. Respond ONLY with a JSON object, no prose, no markdown.

Available intents:
{intent_block}

Output schema (strict JSON):
{{
  "intent": "<one of: {labels}>",
  "rationale": "<short reason in English, <= 120 chars>"
}}

Rules:
- Pick the single best match. If nothing fits, use "unknown".
- Do not invent new intent labels.
- Do not output anything except the JSON object.
"""


def render_system_prompt() -> str:
    intent_block = "\n".join(
        f"- {intent.value}: {desc}" for intent, desc in INTENT_DESCRIPTIONS.items()
    )
    labels = ", ".join(intent.value for intent in Intent)
    return SYSTEM_PROMPT.format(intent_block=intent_block, labels=labels)
