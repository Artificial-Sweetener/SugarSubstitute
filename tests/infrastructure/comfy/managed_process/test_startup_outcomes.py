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

"""Verify terminal outcomes when managed startup fails before spawning."""

from pathlib import Path

import pytest

from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncidentKind
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy import managed_launcher, managed_listener_adoption
from substitute.infrastructure.comfy.managed_process_probe import (
    ManagedListenerProbeResult,
    ManagedListenerStatus,
)
from tests.infrastructure.comfy.managed_process.launch_support import (
    _write_launchable_workspace,
)
from tests.infrastructure.comfy.managed_process.threaded_task_support import (
    _managed_task_factory,
)


@pytest.mark.parametrize("failure", ["missing_workspace", "manager_validation"])
def test_failed_startup_publishes_terminal_incident(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """A finished launch task must expose its failure to readiness consumers."""

    workspace = tmp_path / "comfyui"
    if failure == "manager_validation":
        _write_launchable_workspace(workspace)

    def reject_manager(*_args: object, **_kwargs: object) -> None:
        """Represent a broken installed interpreter at the subprocess boundary."""

        raise RuntimeError("ComfyUI Manager workspace validation failed")

    monkeypatch.setattr(
        managed_launcher, "detect_workspace_manager_runtime", reject_manager
    )
    monkeypatch.setattr(
        managed_listener_adoption,
        "probe_managed_listener",
        lambda **kwargs: ManagedListenerProbeResult(
            status=ManagedListenerStatus.ABSENT, reason="test endpoint absent"
        ),
    )
    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=1),
        workspace=workspace,
        runtime_state_dir=tmp_path / "runtime",
        launch_task_factory=_managed_task_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    try:
        state.wait_until_finished(timeout=5)
        assert state.is_finished
        assert state.proc is None
        result = state.startup_result
        assert result is not None
        assert not result.ready
        assert not result.canceled
        incident = result.fatal_incident
        assert incident is not None
        assert incident.kind is ComfyStartupIncidentKind.LAUNCH_EXCEPTION
        assert incident.exception_type == (
            "FileNotFoundError" if failure == "missing_workspace" else "RuntimeError"
        )
        assert incident.traceback
    finally:
        state.request_stop(reason="test cleanup")


def test_canceled_startup_publishes_cancellation_without_launching(
    tmp_path: Path,
) -> None:
    """Cancellation before the worker starts must resolve without inspecting setup."""

    from substitute.application.execution import (
        CancellationSource,
        ExecutionContext,
        TaskIdentity,
    )
    from substitute.infrastructure.comfy.managed_process_state import (
        LongLivedWork,
        ManagedLongLivedTaskHandle,
    )

    def canceled_factory(
        identity: TaskIdentity,
        context: ExecutionContext,
        work: LongLivedWork[None],
        thread_name: str,
    ) -> ManagedLongLivedTaskHandle:
        """Deliver cancellation before running the real startup operation."""

        def run(cancellation: CancellationSource) -> None:
            """Resolve the task with an already canceled token."""

            cancellation.cancel(reason="user closed startup")
            work(cancellation)

        return _managed_task_factory(identity, context, run, thread_name)

    state = managed_launcher.start_managed_comfy_background(
        endpoint=ComfyEndpoint(host="127.0.0.1", port=1),
        workspace=tmp_path / "missing-workspace",
        runtime_state_dir=tmp_path / "runtime",
        launch_task_factory=canceled_factory,
        process_pump_task_factory=_managed_task_factory,
    )
    try:
        state.wait_until_finished(timeout=5)
        assert state.is_finished
        assert state.proc is None
        assert state.startup_result is not None
        assert state.startup_result.canceled
        assert not state.startup_result.ready
        assert state.startup_result.fatal_incident is None
    finally:
        state.request_stop(reason="test cleanup")
