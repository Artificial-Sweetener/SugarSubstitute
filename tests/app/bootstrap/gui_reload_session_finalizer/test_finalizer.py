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

"""Tests for GUI reload session finalization ownership."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.gui_reload_session_finalizer import (
    GuiReloadFinalizationStart,
    GuiReloadSessionFinalizer,
)
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.app.bootstrap.startup_shutdown import ManagedComfyLease
from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
)
from substitute.application.workspace_state import SessionSaveResult
from tests.support.execution import QueuedTaskSubmitter, never_cancelled


def test_finalizer_rejects_duplicate_while_persistence_is_pending() -> None:
    """Keep one reload lease and one terminal persistence task in flight."""

    submitter = QueuedTaskSubmitter()
    finalizer = _build_finalizer(submitter)

    first = finalizer.begin(object(), on_success=lambda: None, on_failure=lambda: None)
    second = finalizer.begin(object(), on_success=lambda: None, on_failure=lambda: None)

    assert first is GuiReloadFinalizationStart.ACCEPTED
    assert second is GuiReloadFinalizationStart.ALREADY_PENDING
    assert len(submitter.handles) == 1


def test_finalizer_rejects_after_managed_cleanup() -> None:
    """Do not acquire a GUI reload lease after managed cleanup has begun."""

    submitter = QueuedTaskSubmitter()
    lease = ManagedComfyLease(_cleanup_result)
    lease.cleanup()
    finalizer = _build_finalizer(submitter, managed_comfy_lease=lease)

    outcome = finalizer.begin(
        object(),
        on_success=lambda: None,
        on_failure=lambda: None,
    )

    assert outcome is GuiReloadFinalizationStart.LEASE_CLOSED
    assert submitter.handles == ()


def test_finalizer_releases_lease_when_preparation_raises() -> None:
    """Release admission state when terminal persistence cannot be submitted."""

    lease = ManagedComfyLease(_cleanup_result)

    def raise_preparation_error(_main_window: object) -> TaskHandle[SessionSaveResult]:
        """Raise the configured terminal preparation failure."""

        raise RuntimeError("capture failed")

    finalizer = GuiReloadSessionFinalizer(
        managed_comfy_lease=lease,
        begin_session_finalization=raise_preparation_error,
    )

    outcome = finalizer.begin(
        object(),
        on_success=lambda: None,
        on_failure=lambda: None,
    )

    assert outcome is GuiReloadFinalizationStart.PREPARATION_FAILED
    assert lease.gui_reload_active is False


def test_finalizer_publishes_success_and_releases_lease() -> None:
    """Continue reload only after successful persistence and release its lease."""

    submitter = QueuedTaskSubmitter()
    lease = ManagedComfyLease(_cleanup_result)
    finalizer = _build_finalizer(submitter, managed_comfy_lease=lease)
    outcomes: list[str] = []

    assert (
        finalizer.begin(
            object(),
            on_success=lambda: outcomes.append("success"),
            on_failure=lambda: outcomes.append("failure"),
        )
        is GuiReloadFinalizationStart.ACCEPTED
    )
    submitter.handles[0].complete_success(_save_result())

    assert outcomes == ["success"]
    assert lease.gui_reload_active is False


def test_finalizer_publishes_failure_and_releases_lease() -> None:
    """Keep the existing shell when persistence fails and release its lease."""

    submitter = QueuedTaskSubmitter()
    lease = ManagedComfyLease(_cleanup_result)
    finalizer = _build_finalizer(submitter, managed_comfy_lease=lease)
    outcomes: list[str] = []

    assert (
        finalizer.begin(
            object(),
            on_success=lambda: outcomes.append("success"),
            on_failure=lambda: outcomes.append("failure"),
        )
        is GuiReloadFinalizationStart.ACCEPTED
    )
    submitter.handles[0].complete_failed(OSError("disk full"))

    assert outcomes == ["failure"]
    assert lease.gui_reload_active is False


def _build_finalizer(
    submitter: QueuedTaskSubmitter,
    *,
    managed_comfy_lease: ManagedComfyLease | None = None,
) -> GuiReloadSessionFinalizer:
    """Build a finalizer backed by a manually settled task submitter."""

    def begin(_main_window: object) -> TaskHandle[SessionSaveResult]:
        """Submit one deterministic terminal persistence task."""

        return submitter.submit(_request(), cancellation=never_cancelled())

    return GuiReloadSessionFinalizer(
        managed_comfy_lease=managed_comfy_lease or ManagedComfyLease(_cleanup_result),
        begin_session_finalization=begin,
    )


def _request() -> TaskRequest[SessionSaveResult]:
    """Build one manually settled GUI reload persistence request."""

    return TaskRequest(
        identity=TaskIdentity(
            request_id=1,
            domain="session_finalization",
            parts=(("reason", "gui_reload"),),
        ),
        context=ExecutionContext(
            operation="session_finalization",
            reason="gui_reload",
            lane="disk_io_low_priority",
        ),
        work=lambda _token: _save_result(),
    )


def _save_result() -> SessionSaveResult:
    """Build one successful terminal session result."""

    return SessionSaveResult(
        reason="gui_reload",
        elapsed_ms=1.0,
        prerequisite_count=1,
        workflow_count=1,
        persisted=True,
        sequence=1,
    )


def _cleanup_result() -> ManagedComfyCleanupResult:
    """Build one successful managed cleanup result."""

    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        managed_resource_present=True,
        live_process_present=False,
        metadata_present=True,
        used_persisted_metadata=False,
        termination_attempted=True,
        registry_cleared=True,
        pid=1234,
        host="127.0.0.1",
        port=8188,
        workspace=Path("E:/ComfyUI"),
        elapsed_ms=10,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="done",
        technical_detail="done",
        diagnostic_detail="done",
    )
