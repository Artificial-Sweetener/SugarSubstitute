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

"""Persist launcher-owned update state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Self


UPDATE_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class LauncherUpdateState:
    """Represent mutable launcher update state."""

    schema_version: int = UPDATE_STATE_SCHEMA_VERSION
    installed_app_version: str | None = None
    last_update_check_utc: datetime | None = None
    last_successful_update_utc: datetime | None = None
    last_manifest_channel: str | None = None

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load launcher update state or return defaults when absent."""

        if not path.is_file():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Launcher update state must be a JSON object: {path}")
        schema_version = payload.get("schema_version")
        if schema_version != UPDATE_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported launcher update state schema: {schema_version}"
            )
        return cls.from_json(payload)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Self:
        """Build launcher update state from decoded JSON."""

        return cls(
            schema_version=UPDATE_STATE_SCHEMA_VERSION,
            installed_app_version=_optional_string(payload, "installed_app_version"),
            last_update_check_utc=_optional_datetime(
                payload,
                "last_update_check_utc",
            ),
            last_successful_update_utc=_optional_datetime(
                payload,
                "last_successful_update_utc",
            ),
            last_manifest_channel=_optional_string(payload, "last_manifest_channel"),
        )

    def save(self, path: Path) -> None:
        """Persist launcher update state as stable JSON."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def to_json(self) -> dict[str, object]:
        """Return a JSON-safe state payload."""

        return {
            "schema_version": self.schema_version,
            "installed_app_version": self.installed_app_version,
            "last_update_check_utc": _datetime_to_json(self.last_update_check_utc),
            "last_successful_update_utc": _datetime_to_json(
                self.last_successful_update_utc
            ),
            "last_manifest_channel": self.last_manifest_channel,
        }

    def with_update_check(
        self,
        *,
        channel: str,
        checked_at: datetime,
    ) -> LauncherUpdateState:
        """Return state recording one completed manifest check."""

        return LauncherUpdateState(
            installed_app_version=self.installed_app_version,
            last_update_check_utc=_as_utc(checked_at),
            last_successful_update_utc=self.last_successful_update_utc,
            last_manifest_channel=channel,
        )

    def with_installed_payload(
        self,
        *,
        version: str,
        channel: str,
    ) -> LauncherUpdateState:
        """Return state identifying an installed first-run app payload."""

        return LauncherUpdateState(
            installed_app_version=version,
            last_update_check_utc=self.last_update_check_utc,
            last_successful_update_utc=self.last_successful_update_utc,
            last_manifest_channel=channel,
        )

    def with_successful_update(
        self,
        *,
        version: str,
        channel: str,
        completed_at: datetime,
    ) -> LauncherUpdateState:
        """Return state recording one promoted app payload."""

        timestamp = _as_utc(completed_at)
        return LauncherUpdateState(
            installed_app_version=version,
            last_update_check_utc=timestamp,
            last_successful_update_utc=timestamp,
            last_manifest_channel=channel,
        )


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    """Return an optional non-empty string field."""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Launcher update state field must be a string: {key}")
    return value


def _optional_datetime(payload: dict[str, Any], key: str) -> datetime | None:
    """Return an optional UTC datetime field."""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Launcher update state field must be a datetime: {key}")
    return _datetime_from_json(value)


def _datetime_from_json(value: str) -> datetime:
    """Parse one persisted UTC datetime value."""

    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return _as_utc(parsed)


def _datetime_to_json(value: datetime | None) -> str | None:
    """Format one UTC datetime value for stable JSON."""

    if value is None:
        return None
    return _as_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_utc(value: datetime) -> datetime:
    """Return one timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
