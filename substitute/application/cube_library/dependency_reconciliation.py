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

"""Coalesce Cube dependency reconciliation after catalog state changes."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Protocol

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.domain.cube_library import (
    CubeDependencySyncAndCheckRequest,
    CubeDependencySyncAndCheckResult,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("application.cube_library.dependency_reconciliation")


class CubeDependencyReconciliationGateway(Protocol):
    """Run authoritative SugarCubes dependency maintenance."""

    def sync_and_check(
        self,
        request: CubeDependencySyncAndCheckRequest,
    ) -> CubeDependencySyncAndCheckResult | None:
        """Return one authoritative reconciliation result when supported."""


class CubeDependencyReconciliationCoordinator:
    """Run one repair at a time and collapse bursts into one follow-up pass."""

    def __init__(
        self,
        *,
        gateway: CubeDependencyReconciliationGateway,
        result_observer: Callable[[CubeDependencySyncAndCheckResult], None],
        failure_observer: Callable[[BaseException | None], None],
        submitter: TaskSubmitter | None,
    ) -> None:
        """Store the authoritative gateway and bounded execution owner."""

        self._gateway = gateway
        self._result_observer = result_observer
        self._failure_observer = failure_observer
        self._scope = (
            TaskScope(
                submitter=submitter,
                scope_id="cube_dependency_reconciliation",
            )
            if submitter is not None
            else None
        )
        self._lock = Lock()
        self._running = False
        self._run_again = False
        self._closed = False
        self._request_id = 0

    def request(self, *, reason: str) -> None:
        """Request reconciliation without duplicating concurrent maintenance."""

        with self._lock:
            if self._closed:
                return
            if self._running:
                self._run_again = True
                return
            self._running = True
            self._request_id += 1
            request_id = self._request_id
        log_info(
            _LOGGER,
            "Cube dependency reconciliation requested",
            reason=reason,
            request_id=request_id,
        )
        if self._scope is None:
            try:
                result = self._reconcile()
            except Exception as error:
                self._finish_failure(error)
            else:
                self._finish_result(result)
            return
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="cube_dependency_reconciliation",
            ),
            context=ExecutionContext(
                operation="cube_dependency_reconciliation",
                reason=reason,
                lane="cube_library_update",
                safe_fields=(("request_id", request_id),),
            ),
            work=lambda _token: self._reconcile(),
        )
        try:
            handle = self._scope.submit(request)
        except Exception as error:
            self._finish_failure(error)
            return
        handle.add_done_callback(
            self._on_task_finished,
            reason="cube_dependency_reconciliation_completed",
        )

    def close(self) -> None:
        """Stop accepting work and cancel the owned execution scope."""

        with self._lock:
            self._closed = True
            self._run_again = False
        if self._scope is not None:
            self._scope.close(reason="cube_dependency_reconciliation_closed")

    def _reconcile(self) -> CubeDependencySyncAndCheckResult | None:
        """Ask SugarCubes to repair every actionable enabled-Cube requirement."""

        return self._gateway.sync_and_check(
            CubeDependencySyncAndCheckRequest(
                include_versions=True,
                approve_all=True,
                repair=True,
            )
        )

    def _on_task_finished(
        self,
        outcome: TaskOutcome[CubeDependencySyncAndCheckResult | None],
    ) -> None:
        """Publish one settled task and schedule a coalesced follow-up if needed."""

        if outcome.status == "succeeded":
            self._finish_result(outcome.result)
            return
        if outcome.status == "failed":
            self._finish_failure(outcome.error)
            return
        self._finish_failure(None)

    def _finish_result(
        self,
        result: CubeDependencySyncAndCheckResult | None,
    ) -> None:
        """Publish a supported result or a non-locking unsupported outcome."""

        if result is None:
            self._failure_observer(None)
        else:
            self._result_observer(result)
        self._finish_run()

    def _finish_failure(self, error: BaseException | None) -> None:
        """Publish an expected non-locking failure with exception context."""

        if error is not None:
            log_exception(
                _LOGGER,
                "Cube dependency reconciliation failed",
                error=error,
            )
        self._failure_observer(error)
        self._finish_run()

    def _finish_run(self) -> None:
        """Release the running slot and execute one collapsed follow-up request."""

        with self._lock:
            rerun = self._run_again and not self._closed
            self._run_again = False
            self._running = False
        if rerun:
            self.request(reason="coalesced_catalog_change")


__all__ = [
    "CubeDependencyReconciliationCoordinator",
    "CubeDependencyReconciliationGateway",
]
