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

"""Run responsive Comfy environment observations outside the Qt owner thread."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoverySnapshot,
    ComfyEnvironmentService,
)
from substitute.domain.onboarding import (
    ComfyPythonBinding,
    LocalComfyProcess,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.onboarding.comfy_environment_coordinator")
_POLL_INTERVAL_MILLISECONDS = 750


class _MonitorMode(str, Enum):
    """Identify the live observation currently owned by the coordinator."""

    STOPPED = "stopped"
    PREFLIGHT = "preflight"
    ATTACHED_RECOVERY = "attached_recovery"


class ComfyEnvironmentCoordinator(QObject):
    """Coordinate cancellable polling and one-off environment validation tasks."""

    preflight_changed = Signal(object)
    discovery_finished = Signal(object)
    recovery_changed = Signal(object)
    browse_finished = Signal(object)
    termination_finished = Signal(object)
    task_failed = Signal(str)

    def __init__(
        self,
        *,
        service: ComfyEnvironmentService,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None],
        poll_interval_milliseconds: int = _POLL_INTERVAL_MILLISECONDS,
        parent: QObject | None = None,
    ) -> None:
        """Build one scoped execution route and owner-thread polling timer."""

        super().__init__(parent)
        self._service = service
        self._scope = TaskScope(
            submitter=submitter,
            scope_id="onboarding_comfy_environment",
        )
        self._close_submitter = close_submitter
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_milliseconds)
        self._timer.timeout.connect(self._poll)
        self._mode = _MonitorMode.STOPPED
        self._generation = 0
        self._request_id = 0
        self._task_active = False
        self._pending_task: tuple[int, str, Callable[[], object]] | None = None
        self._recovery_workspace: Path | None = None
        self._recovery_binding: ComfyPythonBinding | None = None
        self._observed_processes: tuple[LocalComfyProcess, ...] = ()
        self._shutdown = False
        self.destroyed.connect(lambda _obj=None: self.shutdown())

    def start_preflight(self) -> None:
        """Start continuously observing global local-Comfy process state."""

        self._start_monitor(_MonitorMode.PREFLIGHT)

    def discover_attached_python(self, workspace: Path) -> None:
        """Run one silent conventional discovery request for a selected workspace."""

        self.stop_monitoring()
        self._submit(
            "discovery",
            lambda: self._service.discover_attached_python(workspace),
            queue_if_busy=True,
        )

    def start_attached_recovery(
        self,
        *,
        workspace: Path,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Start live recovery monitoring for one selected Comfy workspace."""

        self._recovery_workspace = workspace
        self._recovery_binding = binding
        self._start_monitor(_MonitorMode.ATTACHED_RECOVERY)

    def validate_browsed_python(self, *, workspace: Path, executable: Path) -> None:
        """Validate a recovery-only file-picker selection asynchronously."""

        self.stop_monitoring()
        self._recovery_workspace = workspace
        self._submit(
            "browse",
            lambda: self._service.validate_browsed_python(
                workspace=workspace,
                executable=executable,
            ),
            queue_if_busy=True,
        )

    def close_observed_processes(self) -> None:
        """Close the latest confidently identified process snapshot explicitly."""

        if not self._observed_processes:
            return
        processes = self._observed_processes
        self._submit(
            "termination",
            lambda: self._service.close_processes(processes),
            queue_if_busy=True,
        )

    def stop_monitoring(self) -> None:
        """Stop polling and ignore any result belonging to the previous page."""

        self._timer.stop()
        self._mode = _MonitorMode.STOPPED
        self._generation += 1
        self._observed_processes = ()
        self._pending_task = None
        self._scope.cancel_all(reason="onboarding_environment_page_changed")

    def shutdown(self) -> None:
        """Cancel scoped work and release the runtime route without blocking Qt."""

        if self._shutdown:
            return
        self._shutdown = True
        self.stop_monitoring()
        self._scope.close(reason="onboarding_environment_closed")
        self._close_submitter()

    def _start_monitor(self, mode: _MonitorMode) -> None:
        """Replace the active monitor and request an immediate observation."""

        self.stop_monitoring()
        self._mode = mode
        self._timer.start()
        self._poll()

    @Slot()
    def _poll(self) -> None:
        """Submit the current monitor observation when its execution route is idle."""

        if self._mode is _MonitorMode.PREFLIGHT:
            self._submit("preflight", self._service.inspect_preflight)
            return
        if self._mode is _MonitorMode.ATTACHED_RECOVERY:
            workspace = self._recovery_workspace
            if workspace is None:
                return
            binding = self._recovery_binding
            self._submit(
                "recovery",
                lambda: self._service.inspect_attached_recovery(
                    workspace=workspace,
                    binding=binding,
                ),
            )

    def _submit(
        self,
        kind: str,
        work: Callable[[], object],
        *,
        queue_if_busy: bool = False,
    ) -> None:
        """Submit one serialized task and route its outcome back through Qt."""

        if self._shutdown:
            return
        if self._task_active:
            if queue_if_busy:
                self._pending_task = (self._generation, kind, work)
            return
        generation = self._generation
        self._request_id += 1
        request: TaskRequest[object] = TaskRequest(
            identity=TaskIdentity(
                request_id=self._request_id,
                domain="onboarding_comfy_environment",
                parts=(("kind", kind), ("generation", generation)),
            ),
            context=ExecutionContext(
                operation="observe_comfy_environment",
                reason=kind,
                lane="onboarding_environment",
                scope_id="onboarding_comfy_environment",
                owner_id="onboarding_window",
                safe_fields=(("kind", kind), ("generation", generation)),
            ),
            work=lambda _cancellation: work(),
        )
        self._task_active = True
        handle = self._scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._deliver_task(generation, kind, outcome),
            reason="onboarding_environment_completed",
        )

    def _deliver_task(
        self,
        generation: int,
        kind: str,
        outcome: TaskOutcome[object],
    ) -> None:
        """Deliver one runtime-published outcome on the coordinator owner thread."""

        self._task_active = False
        if generation != self._generation or self._shutdown:
            self._submit_pending_task()
            return
        if outcome.status == "cancelled":
            self._submit_pending_task()
            return
        if outcome.status == "failed":
            error = outcome.error
            assert error is not None
            log_exception(
                _LOGGER,
                "Comfy environment onboarding task failed",
                error=error,
                task_kind=kind,
            )
            self.task_failed.emit(str(error).strip() or type(error).__name__)
            self._submit_pending_task()
            return
        result = outcome.result
        processes = getattr(result, "processes", None)
        if isinstance(processes, tuple) and all(
            isinstance(item, LocalComfyProcess) for item in processes
        ):
            self._observed_processes = processes
        if kind == "preflight":
            self.preflight_changed.emit(result)
        elif kind == "discovery":
            self.discovery_finished.emit(result)
        elif kind == "recovery":
            if isinstance(result, AttachedPythonRecoverySnapshot):
                self._recovery_binding = result.binding
            self.recovery_changed.emit(result)
        elif kind == "browse":
            self.browse_finished.emit(result)
        elif kind == "termination":
            self.termination_finished.emit(result)
            self._submit_pending_task()
            self._poll()
            return
        self._submit_pending_task()

    def _submit_pending_task(self) -> None:
        """Submit one current user action that waited for an active poll to finish."""

        pending = self._pending_task
        self._pending_task = None
        if pending is None:
            return
        generation, kind, work = pending
        if generation == self._generation and not self._shutdown:
            self._submit(kind, work)


__all__ = ["ComfyEnvironmentCoordinator"]
