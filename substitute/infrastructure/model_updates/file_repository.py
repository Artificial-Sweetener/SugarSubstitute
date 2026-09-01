#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Persist authoritative model usage and opt-in preferences atomically."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic
from sugarsubstitute_shared.model_discovery.models import ModelCategory
from sugarsubstitute_shared.model_updates.models import (
    ModelUsageRecord,
)

_SCHEMA_VERSION = 1


class ModelUpdateStateError(RuntimeError):
    """Report corrupt authoritative update preferences or model usage state."""


class FileModelUsageRepository:
    """Store Generate-derived usage in user settings rather than disposable cache."""

    def __init__(self, settings_dir: Path) -> None:
        """Bind usage state to one installation's preserved user settings."""

        self._path = settings_dir / "model_usage.json"

    def load(self) -> tuple[ModelUsageRecord, ...]:
        """Load exact usage records or fail visibly on corrupt user state."""

        if not self._path.exists():
            return ()
        payload = _read_object(self._path)
        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise ModelUpdateStateError("Unsupported model usage schema.")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise ModelUpdateStateError("Model usage records must be a list.")
        try:
            return tuple(_parse_usage(record) for record in raw_records)
        except (TypeError, ValueError, KeyError) as error:
            raise ModelUpdateStateError("Model usage state is invalid.") from error

    def save(self, records: tuple[ModelUsageRecord, ...]) -> None:
        """Atomically replace usage after validating unique SHA identities."""

        hashes = tuple(record.sha256.casefold() for record in records)
        if len(hashes) != len(set(hashes)):
            raise ModelUpdateStateError(
                "Model usage contains duplicate SHA identities."
            )
        write_json_atomic(
            self._path,
            {
                "schema_version": _SCHEMA_VERSION,
                "records": [_usage_payload(record) for record in records],
            },
        )


def _read_object(path: Path) -> dict[str, object]:
    """Read one authoritative JSON object without substituting corrupt defaults."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelUpdateStateError(
            f"Model update state is unreadable: {path}"
        ) from error
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) for key in payload
    ):
        raise ModelUpdateStateError(f"Model update state must be an object: {path}")
    return {str(key): value for key, value in payload.items()}


def _parse_usage(value: object) -> ModelUsageRecord:
    """Parse one strict usage record."""

    if not isinstance(value, dict):
        raise TypeError("Usage record must be an object.")
    timestamp = datetime.fromisoformat(_string(value, "last_used_at"))
    if timestamp.tzinfo is None:
        raise ValueError("Usage timestamp must include a time zone.")
    usage_count = value.get("usage_count")
    if (
        not isinstance(usage_count, int)
        or isinstance(usage_count, bool)
        or usage_count < 1
    ):
        raise ValueError("Usage count must be positive.")
    return ModelUsageRecord(
        sha256=_sha256(_string(value, "sha256")),
        path=Path(_string(value, "path")),
        category=ModelCategory(_string(value, "category")),
        model_id=_optional_positive_int(value.get("model_id")),
        version_id=_optional_positive_int(value.get("version_id")),
        base_model=_optional_string(value.get("base_model")),
        usage_count=usage_count,
        last_used_at=timestamp.astimezone(UTC),
    )


def _usage_payload(record: ModelUsageRecord) -> dict[str, object]:
    """Serialize one usage record with normalized provider identity."""

    return {
        "sha256": _sha256(record.sha256),
        "path": str(record.path),
        "category": record.category.value,
        "model_id": record.model_id,
        "version_id": record.version_id,
        "base_model": record.base_model,
        "usage_count": record.usage_count,
        "last_used_at": record.last_used_at.astimezone(UTC).isoformat(),
    }


def _string(value: dict[object, object], key: str) -> str:
    """Return one required non-empty string field."""

    selected = value.get(key)
    if not isinstance(selected, str) or not selected.strip():
        raise ValueError(f"Missing string field: {key}")
    return selected


def _optional_string(value: object) -> str | None:
    """Normalize an optional provider string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_positive_int(value: object) -> int | None:
    """Return an optional positive non-boolean integer."""

    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("Provider identifiers must be positive integers.")
    return value


def _sha256(value: str) -> str:
    """Return a normalized exact hash or reject authoritative corruption."""

    normalized = value.casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError("Model usage SHA256 is invalid.")
    return normalized


__all__ = [
    "FileModelUsageRepository",
    "ModelUpdateStateError",
]
