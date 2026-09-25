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

"""Migrate historical session envelopes without changing authored workflow data."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.common import JsonObject
from substitute.domain.workspace_snapshot import SnapshotCodecError


def migrate_session_snapshot_payload(payload: Mapping[str, object]) -> JsonObject:
    """Return a current v2 envelope through explicit forward-only migrations."""

    schema_version = payload.get("schema_version")
    if schema_version == "1":
        migrated: JsonObject = dict(payload)
        migrated["schema_version"] = "2"
        migrated["source_application_version"] = None
        return migrated
    if schema_version == "2":
        return dict(payload)
    raise SnapshotCodecError(
        f"Unsupported session snapshot schema version: {schema_version}"
    )


__all__ = ["migrate_session_snapshot_payload"]
