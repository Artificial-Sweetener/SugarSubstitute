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

"""Verify detached terminal session finalization orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from substitute.application.workspace_state import (
    SessionFinalizationReason,
    SessionFinalizationService,
    SessionSaveResult,
    SessionSaveService,
    SnapshotCapturePort,
)
from substitute.domain.session import SESSION_SNAPSHOT_SCHEMA_VERSION, SessionSnapshot
from substitute.domain.workspace_snapshot import WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from tests.execution_testing import QueuedTaskSubmitter


class _CaptureService:
    """Record owner-thread terminal capture."""

    def __init__(self) -> None:
        """Initialize capture count."""

        self.calls = 0

    def capture(self, port: object) -> SessionSnapshot:
        """Capture one deterministic snapshot."""

        del port
        self.calls += 1
        return _snapshot()


class _Repository:
    """Record detached durable publication."""

    def __init__(self) -> None:
        """Initialize saved snapshots."""

        self.saved: list[SessionSnapshot] = []

    def load(self) -> SessionSnapshot | None:
        """Return no prior snapshot."""

        return None

    def save(self, snapshot: SessionSnapshot) -> None:
        """Record one saved snapshot."""

        self.saved.append(snapshot)


def test_begin_captures_immediately_and_queues_all_persistence() -> None:
    """Return a task handle before any terminal disk work runs."""

    capture = _CaptureService()
    repository = _Repository()
    submitter = QueuedTaskSubmitter()
    save_service = SessionSaveService(
        capture_service=capture,
        repository=repository,
    )
    service = SessionFinalizationService(
        save_service=save_service,
        submitter=submitter,
    )

    handle = service.begin(
        cast(SnapshotCapturePort, object()),
        participants=(),
        reason=SessionFinalizationReason.GUI_RELOAD,
    )

    assert capture.calls == 1
    assert repository.saved == []
    assert handle.is_finished is False
    assert len(submitter.handles) == 1
    assert save_service.accepts_autosave is False

    submitter.handles[0].complete_success(
        SessionSaveResult(
            reason="gui_reload",
            elapsed_ms=1.0,
            prerequisite_count=0,
            workflow_count=0,
            persisted=True,
            sequence=1,
        )
    )

    assert save_service.accepts_autosave is True


def _snapshot() -> SessionSnapshot:
    """Build one deterministic terminal snapshot."""

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
