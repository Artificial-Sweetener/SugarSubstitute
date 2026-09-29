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

"""Verify byte-preserving best-effort session reconciliation."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.app.maintenance.session_recovery import SessionRecoveryService
from sugarsubstitute_shared.session_recovery import SessionRecoveryState


def test_reconcile_migrates_v1_primary_after_preserving_original(
    tmp_path: Path,
) -> None:
    """A historical primary should migrate only after its exact bytes are retained."""

    session_dir = tmp_path / "session"
    session_dir.mkdir()
    primary = session_dir / "session.json"
    original = json.dumps(_v1_payload(), separators=(",", ":"))
    primary.write_text(original, encoding="utf-8")
    recovery_root = tmp_path / "recovery"

    result = SessionRecoveryService().reconcile(
        session_dir=session_dir,
        recovery_root=recovery_root,
        result_path=recovery_root / "result.json",
    )

    assert result.state is SessionRecoveryState.RESTORED_PRIMARY
    assert (recovery_root / "session.json.original").read_text(
        encoding="utf-8"
    ) == original
    migrated = json.loads(primary.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == "2"
    assert migrated["source_application_version"] is None
    assert migrated["workspace"] == _v1_payload()["workspace"]


def test_reconcile_uses_backup_without_destroying_corrupt_primary(
    tmp_path: Path,
) -> None:
    """A usable backup should restore while both source files remain recoverable."""

    session_dir = tmp_path / "session"
    session_dir.mkdir()
    primary = session_dir / "session.json"
    backup = session_dir / "session.json.bak"
    primary.write_text("{not-json", encoding="utf-8")
    backup.write_text(json.dumps(_v1_payload()), encoding="utf-8")
    recovery_root = tmp_path / "recovery"

    result = SessionRecoveryService().reconcile(
        session_dir=session_dir,
        recovery_root=recovery_root,
        result_path=recovery_root / "result.json",
    )

    assert result.state is SessionRecoveryState.RESTORED_BACKUP
    assert (recovery_root / "session.json.original").read_text(
        encoding="utf-8"
    ) == "{not-json"
    assert json.loads(primary.read_text(encoding="utf-8"))["schema_version"] == "2"


def test_reconcile_preserves_unrestorable_session_and_reports_warning(
    tmp_path: Path,
) -> None:
    """Incompatible state should not fail repair or overwrite original bytes."""

    session_dir = tmp_path / "session"
    session_dir.mkdir()
    primary = session_dir / "session.json"
    primary.write_text('{"schema_version":"999"}', encoding="utf-8")
    recovery_root = tmp_path / "recovery"

    result = SessionRecoveryService().reconcile(
        session_dir=session_dir,
        recovery_root=recovery_root,
        result_path=recovery_root / "result.json",
    )

    assert result.state is SessionRecoveryState.PRESERVED_NOT_RESTORED
    assert primary.read_text(encoding="utf-8") == '{"schema_version":"999"}'
    assert (
        recovery_root / "session.json.original"
    ).read_bytes() == primary.read_bytes()


def _v1_payload() -> dict[str, object]:
    """Return the historical session shape used by release 0.23.0."""

    return {
        "schema_version": "1",
        "captured_at": "2026-09-21T12:00:00+00:00",
        "workspace": {
            "schema_version": "1",
            "workflows": [],
            "tab_order": [],
            "active_route": "workflow",
            "active_workflow_id": "",
            "shell_layout": None,
        },
    }
