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

"""Verify forward-compatible session envelope migrations."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.session import migrate_session_snapshot_payload


def test_v1_session_envelope_migrates_to_v2_without_changing_workspace() -> None:
    """Historical workspace bytes must remain semantically untouched."""

    workspace: Mapping[str, object] = {"schema_version": "1", "workflows": []}
    payload: Mapping[str, object] = {
        "schema_version": "1",
        "captured_at": "2026-09-21T12:00:00+00:00",
        "workspace": workspace,
    }

    migrated = migrate_session_snapshot_payload(payload)

    assert migrated == {
        **payload,
        "schema_version": "2",
        "source_application_version": None,
    }
    assert migrated["workspace"] is workspace


def test_current_session_migration_is_idempotent() -> None:
    """Repeated repair passes must preserve an already-current envelope."""

    payload: Mapping[str, object] = {
        "schema_version": "2",
        "captured_at": "2026-09-21T12:00:00+00:00",
        "source_application_version": "0.25.0",
        "workspace": {"schema_version": "1"},
    }

    assert migrate_session_snapshot_payload(
        migrate_session_snapshot_payload(payload)
    ) == dict(payload)
