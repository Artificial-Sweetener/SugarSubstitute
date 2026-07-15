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
    SessionAutosaveService,
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


def test_session_autosave_force_save_captures_and_persists() -> None:
    """Forced save should synchronously persist the captured snapshot."""

    capture = _CaptureService()
    repository = _Repository()
    service = SessionAutosaveService(
        capture_service=capture,
        repository=repository,
    )

    assert service.force_save(cast(SnapshotCapturePort, object())) is True

    assert capture.calls == 1
    assert repository.saved == [_snapshot()]


def test_session_autosave_debounces_pending_saves_until_scheduler_runs() -> None:
    """Repeated requested saves should coalesce while one callback is pending."""

    scheduled: list[object] = []
    capture = _CaptureService()
    repository = _Repository()
    service = SessionAutosaveService(
        capture_service=capture,
        repository=repository,
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
        capture_service=capture,
        repository=repository,
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
