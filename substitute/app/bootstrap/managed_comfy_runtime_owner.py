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

"""Own the mutable managed Comfy process reference and in-place restarts."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.domain.onboarding import ComfyTargetConfiguration, ComfyTargetMode
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("app.bootstrap.managed_comfy_runtime_owner")

ManagedStateCleanup = Callable[[object | None], object]
ManagedStateLauncher = Callable[[], object | None]
ManagedStateStopRequester = Callable[[object | None], None]


class ManagedComfyRuntimeOwner:
    """Coordinate safe process replacement without replacing the application shell."""

    def __init__(
        self,
        *,
        target: ComfyTargetConfiguration,
        submitter: TaskSubmitter,
        request_stop: ManagedStateStopRequester,
        cleanup_state: ManagedStateCleanup,
        confirmed_termination_status: object,
        launch_state: ManagedStateLauncher,
    ) -> None:
        """Store managed lifecycle ports and initialize an empty state reference."""

        self._target = target
        self._scope = TaskScope(
            submitter=submitter,
            scope_id="managed_comfy_crash_recovery",
        )
        self._request_stop = request_stop
        self._cleanup_state = cleanup_state
        self._confirmed_termination_status = confirmed_termination_status
        self._launch_state = launch_state
        self._state: object | None = None
        self._state_observer: Callable[[object | None], None] | None = None
        self._request_id = 0
        self._state_lock = Lock()
        self._lifecycle_lock = Lock()
        self._closed = False

    @property
    def state(self) -> object | None:
        """Return the current managed process state reference."""

        with self._state_lock:
            return self._state

    def set_state(self, state: object | None) -> None:
        """Replace the process state tracked by startup and shutdown owners."""

        with self._state_lock:
            self._state = state
            observer = self._state_observer
        if observer is not None:
            observer(state)

    def bind_state_observer(
        self,
        observer: Callable[[object | None], None],
    ) -> None:
        """Publish future owner state replacements to startup shutdown state."""

        with self._state_lock:
            self._state_observer = observer

    def request_restart(self, *, on_failure: Callable[[], None]) -> None:
        """Schedule one owned managed-local process replacement."""

        if (
            self._target.mode is not ComfyTargetMode.MANAGED_LOCAL
            or not self._target.launch_owned
        ):
            raise RuntimeError("Managed Comfy restart requires an owned local target.")
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("Managed Comfy runtime owner is closed.")
            self._request_id += 1
            request_id = self._request_id
            request: TaskRequest[object | None] = TaskRequest(
                identity=TaskIdentity(
                    request_id=request_id,
                    domain="managed_comfy_crash_recovery",
                ),
                context=ExecutionContext(
                    operation="restart_managed_comfy",
                    reason="connection_lost",
                    lane="startup",
                    safe_fields=(
                        ("host", self._target.endpoint.host),
                        ("port", self._target.endpoint.port),
                    ),
                ),
                work=lambda _token: self._replace_state(request_id),
            )
        handle = self._scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._finish_restart(
                request_id=request_id,
                outcome=outcome,
                on_failure=on_failure,
            ),
            reason="managed_comfy_crash_recovery_finished",
        )
        log_info(
            _LOGGER,
            "Managed Comfy restart scheduled",
            request_id=request_id,
            host=self._target.endpoint.host,
            port=self._target.endpoint.port,
        )

    def close(self) -> None:
        """Cancel pending restart orchestration during runtime shutdown."""

        with self._lifecycle_lock:
            self._closed = True
        self._scope.close(reason="managed_comfy_runtime_owner_close")

    def _replace_state(self, request_id: int) -> object | None:
        """Stop the prior owned process, prove termination, and launch replacement."""

        with self._lifecycle_lock:
            if self._closed:
                return None
            prior_state = self.state
            self._request_stop(prior_state)
            cleanup_result = self._cleanup_state(prior_state)
            termination_status = getattr(cleanup_result, "status", None)
            if termination_status is not self._confirmed_termination_status:
                raise RuntimeError("Managed Comfy termination could not be confirmed.")
            self.set_state(None)
            replacement_state = self._launch_state()
            if replacement_state is None:
                raise RuntimeError("Managed Comfy launch did not return process state.")
            self.set_state(replacement_state)
            log_info(
                _LOGGER,
                "Managed Comfy replacement launched",
                request_id=request_id,
                host=self._target.endpoint.host,
                port=self._target.endpoint.port,
            )
            return replacement_state

    def _finish_restart(
        self,
        *,
        request_id: int,
        outcome: TaskOutcome[object | None],
        on_failure: Callable[[], None],
    ) -> None:
        """Publish orchestration failure while readiness remains monitor-owned."""

        with self._lifecycle_lock:
            if self._closed:
                return
            if outcome.status == "succeeded" and outcome.result is not None:
                return
        log_warning(
            _LOGGER,
            "Managed Comfy restart orchestration failed",
            request_id=request_id,
            status=outcome.status,
            error_type=(type(outcome.error).__name__ if outcome.error else ""),
        )
        on_failure()


__all__ = ["ManagedComfyRuntimeOwner"]
