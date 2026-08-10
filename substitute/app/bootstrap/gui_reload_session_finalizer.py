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

"""Gate GUI replacement on detached terminal session persistence."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from substitute.app.bootstrap.startup_shutdown import (
    GuiReloadLease,
    ManagedComfyLease,
    ManagedComfyLeaseError,
)
from substitute.application.execution import TaskHandle, TaskOutcome
from substitute.application.workspace_state import SessionSaveResult
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.gui_reload_session_finalizer")
SessionFinalizationStarter = Callable[[object], TaskHandle[SessionSaveResult]]


class GuiReloadFinalizationStart(str, Enum):
    """Classify immediate GUI finalization admission outcomes."""

    ACCEPTED = "accepted"
    ALREADY_PENDING = "already_pending"
    LEASE_CLOSED = "lease_closed"
    PREPARATION_FAILED = "preparation_failed"


class GuiReloadSessionFinalizer:
    """Own finalization task and managed-Comfy lease lifetime for one reload."""

    def __init__(
        self,
        *,
        managed_comfy_lease: ManagedComfyLease,
        begin_session_finalization: SessionFinalizationStarter,
    ) -> None:
        """Store terminal persistence and managed-resource lease owners."""

        self._managed_comfy_lease = managed_comfy_lease
        self._begin_session_finalization = begin_session_finalization
        self._pending = False
        self._active_lease: GuiReloadLease | None = None

    @property
    def cleanup_finished(self) -> bool:
        """Return whether managed cleanup prevents another GUI reload."""

        return self._managed_comfy_lease.cleanup_finished

    def begin(
        self,
        main_window: object,
        *,
        on_success: Callable[[], None],
        on_failure: Callable[[], None],
    ) -> GuiReloadFinalizationStart:
        """Acquire the reload lease and submit terminal persistence once."""

        if self._pending:
            log_warning(_LOGGER, "GUI reload finalization is already pending")
            return GuiReloadFinalizationStart.ALREADY_PENDING
        try:
            lease = self._managed_comfy_lease.begin_gui_reload()
        except ManagedComfyLeaseError as error:
            log_warning(
                _LOGGER,
                "GUI reload finalization rejected because the lease is closed",
                error=repr(error),
            )
            return GuiReloadFinalizationStart.LEASE_CLOSED
        self._pending = True
        self._active_lease = lease
        try:
            handle = self._begin_session_finalization(main_window)
        except Exception as error:
            self._finish()
            log_exception(
                _LOGGER,
                "GUI reload session finalization preparation failed",
                error=error,
            )
            return GuiReloadFinalizationStart.PREPARATION_FAILED
        handle.add_done_callback(
            lambda outcome: self._completed(
                outcome,
                on_success=on_success,
                on_failure=on_failure,
            ),
            reason="gui_reload_session_finalization_finished",
        )
        log_info(_LOGGER, "GUI reload session finalization submitted")
        return GuiReloadFinalizationStart.ACCEPTED

    def _completed(
        self,
        outcome: TaskOutcome[SessionSaveResult],
        *,
        on_success: Callable[[], None],
        on_failure: Callable[[], None],
    ) -> None:
        """Publish finalization outcome and always release reload state."""

        try:
            if outcome.status == "succeeded" and outcome.result is not None:
                on_success()
                return
            log_warning(
                _LOGGER,
                "GUI reload session finalization failed",
                status=outcome.status,
                error_type=type(outcome.error).__name__
                if outcome.error is not None
                else "",
            )
            on_failure()
        finally:
            self._finish()

    def _finish(self) -> None:
        """Release pending finalization state and its reload lease."""

        lease = self._active_lease
        self._active_lease = None
        self._pending = False
        if lease is not None:
            lease.close()


__all__ = [
    "GuiReloadFinalizationStart",
    "GuiReloadSessionFinalizer",
    "SessionFinalizationStarter",
]
