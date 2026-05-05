from app.handlers import HANDLERS, dispatch
from app.schemas import Intent


def test_registry_covers_all_known_intents() -> None:
    expected = {i for i in Intent if i is not Intent.UNKNOWN}
    assert set(HANDLERS) == expected


def test_max_speed_handler(store, settings) -> None:
    result = dispatch(Intent.MAX_SPEED, store, settings)
    assert result["units"] == "km/h"
    assert result["max_speed"] >= 180.0 - 1e-3
    assert result["timestamp"] is not None


def test_bad_quality_handler(store, settings) -> None:
    result = dispatch(Intent.BAD_QUALITY, store, settings)
    assert result["total_points"] == 3
    assert result["returned"] == 3
    assert all(p["status"] == 19 for p in result["points"])
    assert all("timestamp" in p and "horizontal_speed" in p for p in result["points"])
    assert 0.0 < result["percentage_of_trip"] <= 100.0


def test_twilight_handler_filters_msk_window(store, settings) -> None:
    result = dispatch(Intent.TWILIGHT_POSITION, store, settings)
    assert result["window_msk"] == "16:00-19:00"
    assert result["total_points"] == 5
    for point in result["points"]:
        assert " 16:" in point["timestamp"]


def test_hard_braking_handler_finds_event(store, settings) -> None:
    result = dispatch(Intent.HARD_BRAKING, store, settings)
    assert result["total_braking_events"] >= 1
    assert result["max_deceleration"] < settings.hard_braking_threshold
    assert result["threshold_ms2"] == settings.hard_braking_threshold
    assert result["events"]
    head = result["events"][0]
    assert head["deceleration"] < settings.hard_braking_threshold
    assert head["speed_before"] >= 100.0
    assert head["speed_after"] != head["speed_before"]


def test_hard_braking_handler_with_no_events(store, settings) -> None:
    relaxed = settings.model_copy(update={"hard_braking_threshold": -1000.0})
    result = dispatch(Intent.HARD_BRAKING, store, relaxed)
    assert result["total_braking_events"] == 0
    assert result["events"] == []
    assert result["threshold_ms2"] == -1000.0


def test_m11_handler(store, settings) -> None:
    result = dispatch(Intent.M11_ROUTE, store, settings)
    assert result["total_points"] >= 5
    assert result["bounding_box"] == settings.m11_bbox()
    assert result["first_seen"] is not None and result["last_seen"] is not None


def test_m11_handler_with_no_match(store, settings) -> None:
    far_away = settings.model_copy(
        update={
            "m11_lat_min": -1.0,
            "m11_lat_max": -0.5,
            "m11_lon_min": -1.0,
            "m11_lon_max": -0.5,
        }
    )
    result = dispatch(Intent.M11_ROUTE, store, far_away)
    assert result["total_points"] == 0
    assert result["returned"] == 0
    assert result["points"] == []
    assert result["first_seen"] is None and result["last_seen"] is None


def test_unknown_intent_returns_helpful_payload(store, settings) -> None:
    result = dispatch(Intent.UNKNOWN, store, settings)
    assert "supported_intents" in result
    assert Intent.MAX_SPEED.value in result["supported_intents"]
    assert Intent.UNKNOWN.value not in result["supported_intents"]
