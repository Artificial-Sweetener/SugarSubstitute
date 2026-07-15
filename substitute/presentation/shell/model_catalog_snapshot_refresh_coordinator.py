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

"""Refresh canonical model catalog snapshots away from the GUI thread."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QObject, Slot

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.model_metadata import ModelCatalogSnapshot
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.shell.model_catalog_snapshot_refresh_coordinator")


class _ModelCatalogSnapshotRefresher(Protocol):
    """Describe canonical model catalog snapshot refresh support."""

    def refresh_snapshot(self, kind: str) -> ModelCatalogSnapshot:
        """Reload and return the canonical snapshot for one model kind."""


class ModelCatalogSnapshotRefreshCoordinator(QObject):
    """Coalesce canonical model catalog refreshes and deliver snapshots to Qt."""

    def __init__(
        self,
        *,
        model_catalog: _ModelCatalogSnapshotRefresher,
        completed: Callable[[ModelCatalogSnapshot, object | None], None],
        parent: QObject | None = None,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Store collaborators and prepare queued Qt completion delivery."""

        super().__init__(parent)
        self._model_catalog = model_catalog
        self._completed_callback = completed
        self._scope = TaskScope(
            submitter=submitter,
            scope_id=f"model_catalog_snapshot_refresh_{id(self):x}",
        )
        self._close_submitter = close_submitter
        self._queued_request: tuple[str, object | None] | None = None
        self._running = False
        self._shutdown_requested = False
        self._active_request_id = 0
        if parent is not None:
            parent.destroyed.connect(self.shutdown)

    def request_refresh(self, kind: str, context: object | None = None) -> None:
        """Request one coalesced canonical model snapshot refresh."""

        normalized_kind = kind.strip()
        if self._shutdown_requested or not normalized_kind:
            return
        self._queued_request = (normalized_kind, context)
        if self._running:
            return
        self._start_next_refresh()

    @Slot()
    def shutdown(self) -> None:
        """Stop accepting work and release owned execution resources."""

        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._queued_request = None
        self._scope.close(reason="model_catalog_snapshot_refresh_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None

    def _start_next_refresh(self) -> None:
        """Submit the latest queued request if no refresh is active."""

        if self._shutdown_requested or self._running:
            return
        queued_request = self._queued_request
        self._queued_request = None
        if queued_request is None:
            return
        kind, context = queued_request
        self._running = True
        self._active_request_id += 1
        request_id = self._active_request_id
        task_request = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="model_catalog",
                parts=(("kind", kind),),
            ),
            context=ExecutionContext(
                operation="refresh_model_catalog_snapshot",
                reason="model_catalog_change",
                lane="model_catalog",
                safe_fields=(("kind", kind), ("request_id", request_id)),
            ),
            work=lambda _token: self._model_catalog.refresh_snapshot(kind),
        )
        handle = self._scope.submit(task_request)
        handle.add_done_callback(
            lambda outcome: self._deliver_task_outcome(
                request_id=request_id,
                context=context,
                outcome=outcome,
            ),
            reason="model_catalog_snapshot_refresh_completed",
        )
        log_debug(
            _LOGGER,
            "Started canonical model catalog snapshot refresh",
            request_id=request_id,
            kind=kind,
        )

    def _deliver_task_outcome(
        self,
        *,
        request_id: int,
        context: object | None,
        outcome: TaskOutcome[ModelCatalogSnapshot],
    ) -> None:
        """Convert one execution outcome into the existing delivery path."""

        snapshot: ModelCatalogSnapshot | None = outcome.result
        error: BaseException | None = outcome.error
        if outcome.cancelled:
            error = RuntimeError(outcome.cancellation_reason or "cancelled")
        self._deliver_completed_refresh(request_id, snapshot, error, context)

    @Slot(int, object, object, object)
    def _deliver_completed_refresh(
        self,
        request_id: int,
        snapshot: object,
        error: object,
        context: object,
    ) -> None:
        """Deliver a refreshed canonical snapshot on the GUI thread."""

        if request_id != self._active_request_id or self._shutdown_requested:
            return
        self._running = False
        if isinstance(error, BaseException):
            log_warning(
                _LOGGER,
                "Canonical model catalog snapshot refresh failed",
                request_id=request_id,
                error=repr(error),
            )
            self._start_next_refresh()
            return
        model_snapshot = cast(ModelCatalogSnapshot, snapshot)
        self._completed_callback(model_snapshot, context)
        log_debug(
            _LOGGER,
            "Completed canonical model catalog snapshot refresh",
            request_id=request_id,
            kind=model_snapshot.kind,
            generation=model_snapshot.generation,
        )
        self._start_next_refresh()


__all__ = ["ModelCatalogSnapshotRefreshCoordinator"]
