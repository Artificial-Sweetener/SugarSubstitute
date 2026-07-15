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

"""Schedule and coalesce workflow surface refresh work."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.shell.workflow_surface_refresh_scheduler")

SurfaceRefreshCallback = Callable[[str, bool, Callable[[], None] | None], None]


@dataclass(frozen=True, slots=True)
class WorkflowSurfaceRefreshRequest:
    """Describe one pending workflow surface refresh request."""

    workflow_id: str
    force_refresh: bool
    reason: str
    on_complete: Callable[[], None] | None
    token: int


class WorkflowSurfaceRefreshScheduler(QObject):
    """Coalesce deferred workflow surface refresh requests."""

    def __init__(
        self,
        *,
        active_workflow_id: Callable[[], str],
        refresh_surface: SurfaceRefreshCallback,
        parent: QObject | None = None,
        interval_ms: int = 0,
    ) -> None:
        """Initialize the GUI-thread timer and refresh collaborators."""

        super().__init__(parent)
        self._active_workflow_id = active_workflow_id
        self._refresh_surface = refresh_surface
        self._interval_ms = max(0, int(interval_ms))
        self._next_token = 0
        self._pending: WorkflowSurfaceRefreshRequest | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self.flush)

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Schedule refresh for the latest workflow id."""

        self._next_token += 1
        self._pending = WorkflowSurfaceRefreshRequest(
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            reason=reason,
            on_complete=on_complete,
            token=self._next_token,
        )
        log_debug(
            _LOGGER,
            "scheduled workflow surface refresh",
            workflow_id=workflow_id,
            force_refresh=force_refresh,
            reason=reason,
            token=self._next_token,
        )
        self._timer.start(self._interval_ms)

    def cancel(self, workflow_id: str | None = None) -> None:
        """Cancel pending refresh work."""

        pending = self._pending
        if pending is None:
            return
        if workflow_id is not None and pending.workflow_id != workflow_id:
            return
        self._pending = None
        self._timer.stop()
        log_debug(
            _LOGGER,
            "cancelled workflow surface refresh",
            workflow_id=pending.workflow_id,
            requested_workflow_id=workflow_id,
            token=pending.token,
        )

    def flush(self) -> None:
        """Run the latest pending workflow surface refresh when it is still current."""

        pending = self._pending
        if pending is None:
            return
        self._pending = None
        active_workflow_id = self._active_workflow_id()
        if pending.workflow_id != active_workflow_id:
            log_debug(
                _LOGGER,
                "skipped stale workflow surface refresh",
                workflow_id=pending.workflow_id,
                active_workflow_id=active_workflow_id,
                reason=pending.reason,
                token=pending.token,
            )
            return
        log_debug(
            _LOGGER,
            "running workflow surface refresh",
            workflow_id=pending.workflow_id,
            force_refresh=pending.force_refresh,
            reason=pending.reason,
            token=pending.token,
        )
        self._refresh_surface(
            pending.workflow_id,
            pending.force_refresh,
            pending.on_complete,
        )


__all__ = [
    "SurfaceRefreshCallback",
    "WorkflowSurfaceRefreshRequest",
    "WorkflowSurfaceRefreshScheduler",
]
