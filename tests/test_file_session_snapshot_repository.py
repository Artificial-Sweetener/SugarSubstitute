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

"""Tests for filesystem-backed session snapshot persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from substitute.domain.session import (
    SESSION_SNAPSHOT_SCHEMA_VERSION,
    SessionSnapshot,
)
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.infrastructure.persistence.file_session_snapshot_repository import (
    FileSessionSnapshotRepository,
)


def test_file_session_snapshot_repository_returns_none_when_missing(
    tmp_path: Path,
) -> None:
    """Missing session files should not block startup."""

    repository = FileSessionSnapshotRepository(tmp_path / "session")

    assert repository.load() is None


def test_file_session_snapshot_repository_round_trips_stable_json(
    tmp_path: Path,
) -> None:
    """Saved snapshots should load back from the primary session file."""

    session_dir = tmp_path / "session"
    repository = FileSessionSnapshotRepository(session_dir)
    snapshot = _snapshot(active_route="workflow:wf-1")

    repository.save(snapshot)

    session_path = session_dir / "session.json"
    assert session_path.exists()
    assert session_path.read_text(encoding="utf-8").endswith("\n")
    assert repository.load() == snapshot


def test_file_session_snapshot_repository_recovers_from_backup(
    tmp_path: Path,
) -> None:
    """Corrupt primary JSON should fall back to the prior backup snapshot."""

    session_dir = tmp_path / "session"
    repository = FileSessionSnapshotRepository(session_dir)
    first = _snapshot(active_route="workflow:first")
    second = _snapshot(active_route="workflow:second")
    repository.save(first)
    repository.save(second)
    session_path = session_dir / "session.json"
    session_path.write_text("{not json", encoding="utf-8")

    recovered = repository.load()

    assert recovered == first


def test_file_session_snapshot_repository_returns_none_when_primary_and_backup_corrupt(
    tmp_path: Path,
) -> None:
    """Invalid session state should be ignored when recovery is unavailable."""

    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "session.json").write_text("{not json", encoding="utf-8")
    (session_dir / "session.json.bak").write_text("{also not json", encoding="utf-8")
    repository = FileSessionSnapshotRepository(session_dir)

    assert repository.load() is None


def _snapshot(*, active_route: str) -> SessionSnapshot:
    """Build one deterministic session snapshot for repository tests."""

    return SessionSnapshot(
        schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
        captured_at=datetime(2026, 5, 8, 12, tzinfo=timezone.utc),
        workspace=WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(),
            tab_order=(),
            active_route=active_route,
            shell_layout=None,
        ),
    )
