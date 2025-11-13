"""Telemetry normalisation toolkit for the visitor constellation.

The module exposes a thin Pydantic-powered schema and a normalisation helper
so downstream services can emit consistent telemetry envelopes without
re-writing the same coercion logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

DEFAULT_TELEMETRY_VERSION = "0.1.0"


class TelemetryEvent(BaseModel):
    """Pydantic model describing the canonical telemetry envelope."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    event_id: str = Field(alias="id")
    source: str
    action: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def _coerce_timestamp(cls, value: Any) -> datetime:
        """Accept string, epoch seconds, or datetime and return UTC-aware timestamp."""
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=UTC)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        msg = f"Unsupported timestamp value: {value!r}"
        raise ValueError(msg)

    @field_validator("event_id")
    @classmethod
    def _strip_event_id(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            msg = "event_id may not be empty"
            raise ValueError(msg)
        return clean

    @field_validator("source", "action")
    @classmethod
    def _strip_required_fields(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            msg = "source/action cannot be blank"
            raise ValueError(msg)
        return clean


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def normalize_payload(
    event: Mapping[str, Any],
    *,
    telemetry_version: str | None = None,
    ingested_at: datetime | None = None,
) -> dict[str, Any]:
    """Normalise a raw telemetry payload into the canonical envelope.

    Parameters
    ----------
    event:
        Mapping containing raw telemetry data. Must include ``id``, ``source``,
        ``action``, and ``timestamp``.
    telemetry_version:
        Optional version string to embed in the envelope. Defaults to
        :data:`DEFAULT_TELEMETRY_VERSION`.
    ingested_at:
        Optional datetime describing when the event entered the pipeline. If not
        supplied the current UTC time is used.
    """

    try:
        model = TelemetryEvent.model_validate(event)  # type: ignore[attr-defined]
    except ValidationError as exc:  # pragma: no cover - provide stable error type
        raise ValueError(str(exc)) from exc

    normalized_ingested_at = _ensure_utc(ingested_at) if ingested_at else datetime.now(tz=UTC)
    envelope = {
        "telemetry_version": telemetry_version or DEFAULT_TELEMETRY_VERSION,
        "event_id": model.event_id,
        "source": model.source,
        "action": model.action,
        "timestamp": model.timestamp.astimezone(UTC).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "ingested_at": normalized_ingested_at.astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "payload": model.payload,
        "metadata": model.metadata,
    }
    return envelope


__all__ = [
    "DEFAULT_TELEMETRY_VERSION",
    "TelemetryEvent",
    "normalize_payload",
]
