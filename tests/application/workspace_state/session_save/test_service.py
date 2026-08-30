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

"""Verify authoritative ordering and freshness for session persistence."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import cast

import pytest

from substitute.application.workspace_state import (
    PreparedSessionPersistence,
    SessionSaveService,
    SnapshotCapturePort,
)
from substitute.domain.session import SESSION_SNAPSHOT_SCHEMA_VERSION, SessionSnapshot
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


class _CaptureService:
    """Capture snapshots whose routes identify their preparation order."""

    def __init__(self) -> None:
        """Initialize capture ordering."""

        self.calls = 0

    def capture(self, port: object) -> SessionSnapshot:
        """Return the next ordered snapshot."""

        del port
        self.calls += 1
        snapshot = _snapshot()
        return replace(
            snapshot,
            workspace=replace(snapshot.workspace, active_route=str(self.calls)),
        )


class _Repository:
    """Record durable snapshot publication."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared ordering log."""

        self.events = events
        self.saved: list[SessionSnapshot] = []

    def load(self) -> SessionSnapshot | None:
        """Return no persisted fixture."""

        return None

    def save(self, snapshot: SessionSnapshot) -> None:
        """Record one durable session publication."""

        self.events.append(f"session-{snapshot.workspace.active_route}")
        self.saved.append(snapshot)


class _Participant:
    """Prepare one prerequisite event."""

    def __init__(self, events: list[str], name: str, *, fails: bool = False) -> None:
        """Store fixture behavior."""

        self._events = events
        self._name = name
        self._fails = fails

    def prepare_session_persistence(self) -> PreparedSessionPersistence:
        """Capture one detached prerequisite callback."""

        def persist() -> None:
            """Record or fail prerequisite persistence."""

            self._events.append(self._name)
            if self._fails:
                raise OSError("fixture persistence failed")

        return PreparedSessionPersistence(self._name, persist)


def test_session_save_persists_prerequisites_before_snapshot() -> None:
    """Publish the archive prerequisite before its referencing session JSON."""

    events: list[str] = []
    service = SessionSaveService(
        capture_service=_CaptureService(),
        repository=_Repository(events),
    )
    prepared = service.prepare(
        cast(SnapshotCapturePort, object()),
        participants=(_Participant(events, "archive"),),
        reason="test",
    )

    result = service.persist(prepared)

    assert events == ["archive", "session-1"]
    assert result.persisted is True


def test_session_save_failure_does_not_publish_snapshot() -> None:
    """Fail closed when a prerequisite cannot become durable."""

    events: list[str] = []
    repository = _Repository(events)
    service = SessionSaveService(
        capture_service=_CaptureService(),
        repository=repository,
    )
    prepared = service.prepare(
        cast(SnapshotCapturePort, object()),
        participants=(_Participant(events, "archive", fails=True),),
        reason="test",
    )

    with pytest.raises(OSError, match="fixture persistence failed"):
        service.persist(prepared)

    assert repository.saved == []


def test_newer_save_prevents_late_older_save_from_overwriting_it() -> None:
    """Skip a stale autosave that reaches disk after terminal finalization."""

    events: list[str] = []
    repository = _Repository(events)
    service = SessionSaveService(
        capture_service=_CaptureService(),
        repository=repository,
    )
    older = service.prepare(
        cast(SnapshotCapturePort, object()),
        participants=(_Participant(events, "old-archive"),),
        reason="autosave",
    )
    newer = service.prepare(
        cast(SnapshotCapturePort, object()),
        participants=(_Participant(events, "new-archive"),),
        reason="shutdown",
    )

    newest_result = service.persist(newer)
    stale_result = service.persist(older)

    assert newest_result.persisted is True
    assert stale_result.persisted is False
    assert events == ["new-archive", "session-2"]
    assert repository.saved == [newer.snapshot]


def test_failed_newer_save_does_not_suppress_retryable_older_save() -> None:
    """Advance freshness only after the complete save becomes durable."""

    events: list[str] = []
    service = SessionSaveService(
        capture_service=_CaptureService(),
        repository=_Repository(events),
    )
    older = service.prepare(
        cast(SnapshotCapturePort, object()),
        reason="autosave",
    )
    newer = service.prepare(
        cast(SnapshotCapturePort, object()),
        participants=(_Participant(events, "new-archive", fails=True),),
        reason="shutdown",
    )

    with pytest.raises(OSError):
        service.persist(newer)
    result = service.persist(older)

    assert result.persisted is True
    assert events == ["new-archive", "session-1"]


def test_terminal_save_suppresses_later_autosaves_until_released() -> None:
    """Prevent a late debounce from overwriting terminal session authority."""

    events: list[str] = []
    service = SessionSaveService(
        capture_service=_CaptureService(),
        repository=_Repository(events),
    )
    terminal = service.prepare(
        cast(SnapshotCapturePort, object()),
        reason="gui_reload",
        terminal=True,
    )
    late_autosave = service.prepare(
        cast(SnapshotCapturePort, object()),
        reason="autosave",
    )

    service.persist(terminal)
    suppressed = service.persist(late_autosave)
    service.release_terminal(terminal.sequence)
    resumed = service.prepare(
        cast(SnapshotCapturePort, object()),
        reason="autosave",
    )

    assert late_autosave.suppressed is True
    assert suppressed.persisted is False
    assert resumed.suppressed is False
    assert events == ["session-1"]


def test_failed_terminal_capture_releases_autosaves() -> None:
    """Do not leave a live shell muted when GUI finalization cannot prepare."""

    class FailingCapture:
        """Raise from terminal owner-thread capture."""

        def capture(self, port: object) -> SessionSnapshot:
            """Raise one deterministic capture failure."""

            del port
            raise RuntimeError("capture failed")

    service = SessionSaveService(
        capture_service=FailingCapture(),
        repository=_Repository([]),
    )

    with pytest.raises(RuntimeError, match="capture failed"):
        service.prepare(
            cast(SnapshotCapturePort, object()),
            reason="gui_reload",
            terminal=True,
        )

    assert service.accepts_autosave is True


def _snapshot() -> SessionSnapshot:
    """Build one deterministic session snapshot."""

    return SessionSnapshot(
        schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
        captured_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        workspace=WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(),
            tab_order=(),
            active_route="",
            shell_layout=None,
        ),
    )
