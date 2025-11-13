from __future__ import annotations

from datetime import datetime

import pytest
from x_make_telemetry_vector_x import (
    DEFAULT_TELEMETRY_VERSION,
    TelemetryEvent,
    normalize_payload,
)


def test_normalize_payload_accepts_iso_timestamp() -> None:
    event = {
        "id": "abc-123",
        "source": "github_clones",
        "action": "clone",
        "timestamp": "2025-11-12T10:30:00Z",
        "payload": {"foo": "bar"},
        "metadata": {"observer": "navarro"},
    }

    normalized = normalize_payload(event)

    assert normalized["telemetry_version"] == DEFAULT_TELEMETRY_VERSION
    assert normalized["event_id"] == "abc-123"
    assert normalized["source"] == "github_clones"
    assert normalized["action"] == "clone"
    assert normalized["timestamp"] == "2025-11-12T10:30:00Z"
    assert normalized["payload"] == {"foo": "bar"}
    assert normalized["metadata"] == {"observer": "navarro"}


def test_normalize_payload_coerces_epoch_timestamp() -> None:
    event = {
        "id": "xyz-789",
        "source": "visitor",
        "action": "ingest",
        "timestamp": 1_700_000_000,
    }

    normalized = normalize_payload(event)
    assert normalized["timestamp"] == "2023-11-14T22:13:20Z"


def test_normalize_payload_supports_naive_datetime() -> None:
    naive_dt = datetime(2025, 11, 12, 8, 45, 0)
    event = {
        "id": "naive",
        "source": "lab",
        "action": "emit",
        "timestamp": naive_dt,
    }

    normalized = normalize_payload(event, telemetry_version="custom", ingested_at=naive_dt)
    assert normalized["telemetry_version"] == "custom"
    assert normalized["timestamp"] == "2025-11-12T08:45:00Z"
    assert normalized["ingested_at"] == "2025-11-12T08:45:00Z"


def test_normalize_payload_rejects_bad_timestamp() -> None:
    event = {
        "id": "bad",
        "source": "lab",
        "action": "emit",
        "timestamp": object(),
    }

    with pytest.raises(ValueError):
        normalize_payload(event)


def test_model_enforces_non_empty_strings() -> None:
    with pytest.raises(ValueError):
        TelemetryEvent.model_validate({
            "id": " ",
            "source": "lab",
            "action": "emit",
            "timestamp": "2025-11-12T08:45:00Z",
        })

    with pytest.raises(ValueError):
        TelemetryEvent.model_validate({
            "id": "event",
            "source": "",
            "action": "emit",
            "timestamp": "2025-11-12T08:45:00Z",
        })
