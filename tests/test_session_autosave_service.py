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

"""Tests for session autosave coordination."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

import pytest

from substitute.application.workspace_state import (
    PreparedSessionPersistence,
    SessionAutosaveService,
    SessionSaveService,
    SnapshotCapturePort,
)
from substitute.domain.session import (
    SESSION_SNAPSHOT_SCHEMA_VERSION,
    SessionSnapshot,
)
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


@dataclass
class _CaptureService:
    """Return a deterministic snapshot and record capture calls."""

    calls: int = 0

    def capture(self, port: object) -> SessionSnapshot:
        """Capture one deterministic snapshot."""

        del port
        self.calls += 1
        return _snapshot()


class _Repository:
    """Record saved snapshots."""

    def __init__(self) -> None:
        """Initialize save recording."""

        self.saved: list[SessionSnapshot] = []

    def load(self) -> SessionSnapshot | None:
        """Return no persisted snapshot."""

        return None

    def save(self, snapshot: SessionSnapshot) -> None:
        """Record one saved snapshot."""

        self.saved.append(snapshot)


class _PersistenceParticipant:
    """Prepare detached prerequisite work and record background execution."""

    def __init__(self, events: list[str]) -> None:
        """Store shared ordering events."""
        self.events = events
        self.prepared = 0

    def prepare_session_persistence(self) -> PreparedSessionPersistence:
        """Capture one background-safe persistence callback."""
        self.prepared += 1
        revision = self.prepared
        return PreparedSessionPersistence(
            "fixture",
            lambda: self.events.append(f"participant-{revision}"),
        )


class _FailingPersistenceParticipant:
    """Raise from detached persistence after successful owner-thread capture."""

    def prepare_session_persistence(self) -> PreparedSessionPersistence:
        """Return detached work that deterministically fails."""

        def fail() -> None:
            """Raise the fixture persistence failure."""

            raise OSError("fixture persistence failed")

        return PreparedSessionPersistence("failing_fixture", fail)


def test_session_autosave_debounces_pending_saves_until_scheduler_runs() -> None:
    """Repeated requested saves should coalesce while one callback is pending."""

    scheduled: list[object] = []
    capture = _CaptureService()
    repository = _Repository()
    service = SessionAutosaveService(
        save_service=SessionSaveService(
            capture_service=capture,
            repository=repository,
        ),
        schedule_debounced=scheduled.append,
    )

    port = cast(SnapshotCapturePort, object())
    service.request_save(port)
    service.request_save(port)

    assert len(scheduled) == 1
    assert capture.calls == 0
    callback = scheduled.pop()
    assert callable(callback)
    callback()
    assert capture.calls == 0
    assert len(scheduled) == 1
    settled_callback = scheduled.pop()
    assert callable(settled_callback)
    settled_callback()
    assert capture.calls == 1
    assert repository.saved == [_snapshot()]


def test_requested_session_autosave_success_is_quiet_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Routine autosave capture and persistence should not fill INFO logs."""

    scheduled: list[object] = []
    capture = _CaptureService()
    repository = _Repository()
    service = SessionAutosaveService(
        save_service=SessionSaveService(
            capture_service=capture,
            repository=repository,
        ),
        schedule_debounced=scheduled.append,
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.application.workspace_state.session_autosave_service",
    )

    service.request_save(cast(SnapshotCapturePort, object()))
    callback = scheduled.pop()
    assert callable(callback)
    callback()

    assert capture.calls == 1
    assert repository.saved == [_snapshot()]
    assert caplog.records == []


def test_session_prerequisite_is_prepared_after_debounce_and_persisted_first() -> None:
    """Coalesce owner-thread capture and preserve background write ordering."""

    scheduled: list[object] = []
    persistence: list[object] = []
    events: list[str] = []
    capture = _CaptureService()
    participant = _PersistenceParticipant(events)

    class OrderedRepository(_Repository):
        """Record repository ordering beside the prerequisite."""

        def save(self, snapshot: SessionSnapshot) -> None:
            """Record session persistence after prerequisite work."""
            events.append("session")
            super().save(snapshot)

    repository = OrderedRepository()
    service = SessionAutosaveService(
        save_service=SessionSaveService(
            capture_service=capture,
            repository=repository,
        ),
        schedule_debounced=scheduled.append,
        schedule_persistence=persistence.append,
    )
    port = cast(SnapshotCapturePort, object())

    for _ in range(100):
        service.request_save(port, participants=(participant,))

    assert participant.prepared == 0
    assert len(scheduled) == 1
    stale_debounce = scheduled.pop()
    assert callable(stale_debounce)
    stale_debounce()
    assert participant.prepared == 0
    assert len(scheduled) == 1
    settled_debounce = scheduled.pop()
    assert callable(settled_debounce)
    settled_debounce()
    assert participant.prepared == 1
    assert events == []
    assert len(persistence) == 1
    persist = persistence.pop()
    assert callable(persist)
    persist()

    assert events == ["participant-1", "session"]
    assert repository.saved == [_snapshot()]


def test_edit_arriving_during_persistence_schedules_a_fresh_capture() -> None:
    """Never lose document changes made while an earlier archive is writing."""

    scheduled: list[object] = []
    persistence: list[object] = []
    participant = _PersistenceParticipant([])
    service = SessionAutosaveService(
        save_service=SessionSaveService(
            capture_service=_CaptureService(),
            repository=_Repository(),
        ),
        schedule_debounced=scheduled.append,
        schedule_persistence=persistence.append,
    )
    port = cast(SnapshotCapturePort, object())
    service.request_save(port, participants=(participant,))
    first_debounce = scheduled.pop()
    assert callable(first_debounce)
    first_debounce()

    service.request_save(port, participants=(participant,))
    blocked_debounce = scheduled.pop()
    assert callable(blocked_debounce)
    blocked_debounce()
    assert len(scheduled) == 1
    assert participant.prepared == 1

    first_persist = persistence.pop()
    assert callable(first_persist)
    first_persist()
    retry = scheduled.pop()
    assert callable(retry)
    retry()

    assert participant.prepared == 2
    assert len(persistence) == 1


def test_failed_participant_blocks_snapshot_and_releases_save_guard() -> None:
    """A prerequisite failure must not publish a mismatched session snapshot."""

    scheduled: list[object] = []
    persistence: list[object] = []
    capture = _CaptureService()
    repository = _Repository()
    service = SessionAutosaveService(
        save_service=SessionSaveService(
            capture_service=capture,
            repository=repository,
        ),
        schedule_debounced=scheduled.append,
        schedule_persistence=persistence.append,
    )
    port = cast(SnapshotCapturePort, object())
    service.request_save(port, participants=(_FailingPersistenceParticipant(),))
    debounce = scheduled.pop()
    assert callable(debounce)
    debounce()
    failed_persistence = persistence.pop()
    assert callable(failed_persistence)
    failed_persistence()

    assert repository.saved == []
    service.request_save(port)
    retry_debounce = scheduled.pop()
    assert callable(retry_debounce)
    retry_debounce()
    retry_persistence = persistence.pop()
    assert callable(retry_persistence)
    retry_persistence()

    assert capture.calls == 2
    assert repository.saved == [_snapshot()]


def _snapshot() -> SessionSnapshot:
    """Build one deterministic session snapshot for autosave tests."""

    return SessionSnapshot(
        schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
        captured_at=datetime(2026, 5, 8, 12, tzinfo=timezone.utc),
        workspace=WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(),
            tab_order=(),
            active_route="",
            shell_layout=None,
        ),
    )
