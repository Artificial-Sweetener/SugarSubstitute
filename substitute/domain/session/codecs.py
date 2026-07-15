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

"""Encode and decode mutable session snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from substitute.domain.common import JsonObject
from substitute.domain.session.models import SessionSnapshot
from substitute.domain.workspace_snapshot import (
    SnapshotCodecError,
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)

SESSION_SNAPSHOT_SCHEMA_VERSION = "1"


def session_snapshot_to_json(snapshot: SessionSnapshot) -> JsonObject:
    """Return a JSON-ready mapping for one session snapshot."""

    return {
        "schema_version": snapshot.schema_version,
        "captured_at": snapshot.captured_at.isoformat(),
        "workspace": workspace_snapshot_to_json(snapshot.workspace),
    }


def session_snapshot_from_json(payload: Mapping[str, object]) -> SessionSnapshot:
    """Build a session snapshot from a decoded JSON mapping."""

    schema_version = _required_str(payload, "schema_version")
    if schema_version != SESSION_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotCodecError(
            f"Unsupported session snapshot schema version: {schema_version}"
        )
    return SessionSnapshot(
        schema_version=schema_version,
        captured_at=_datetime_from_text(_required_str(payload, "captured_at")),
        workspace=workspace_snapshot_from_json(_required_mapping(payload, "workspace")),
    )


def _required_str(payload: Mapping[str, object], key: str) -> str:
    """Return one required string field from a mapping."""

    value = payload.get(key)
    if not isinstance(value, str):
        raise SnapshotCodecError(f"Missing or invalid string field: {key}")
    return value


def _required_mapping(
    payload: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required object field from a mapping."""

    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise SnapshotCodecError(f"Missing or invalid object field: {key}")
    return value


def _datetime_from_text(value: str) -> datetime:
    """Parse one ISO datetime from session JSON."""

    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise SnapshotCodecError(f"Invalid captured_at value: {value}") from error


__all__ = [
    "SESSION_SNAPSHOT_SCHEMA_VERSION",
    "session_snapshot_from_json",
    "session_snapshot_to_json",
]
