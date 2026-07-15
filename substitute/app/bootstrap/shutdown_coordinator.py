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

"""Coordinate responsive shell shutdown while managed ComfyUI cleans up."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from itertools import count
from typing import Protocol

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QWidget

from substitute.app.bootstrap.lifecycle import (
    CleanupBypassFn,
    CleanupFn,
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)
from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.presentation.shell.shutdown_progress_dialog import (
    ShutdownProgressDialog,
)
from substitute.presentation.shell.shutdown_recovery_dialog import (
    ShutdownRecoveryDialog,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.shutdown_coordinator")
_SLOW_SHUTDOWN_THRESHOLD_MS = 500
_CLEANUP_ATTEMPT_TIMEOUT_MS = 15000


class ShutdownUiState(Enum):
    """Describe the coordinator-owned UI state for shell shutdown."""

    IDLE = "idle"
    RUNNING_HIDDEN = "running_hidden"
    RUNNING_VISIBLE = "running_visible"
    RECOVERY_VISIBLE = "recovery_visible"
    FINALIZING_EXIT = "finalizing_exit"


class AppQuitProtocol(Protocol):
    """Describe the application surface needed by coordinated shutdown."""

    def quit(self) -> None:
        """Request that the application event loop exit."""


class ShutdownProgressDialogProtocol(Protocol):
    """Describe the delayed shutdown progress surface."""

    def show(self) -> None:
        """Show the shutdown surface."""

    def raise_(self) -> None:
        """Raise the shutdown surface above sibling windows."""

    def activateWindow(self) -> None:
        """Focus the shutdown surface."""

    def allow_close(self) -> None:
        """Permit programmatic close after cleanup completes."""

    def close(self) -> bool:
        """Close the shutdown surface."""


class ShutdownRecoveryDialogProtocol(Protocol):
    """Describe the shutdown recovery surface."""

    def show(self) -> None:
        """Show the recovery surface."""

    def raise_(self) -> None:
        """Raise the recovery surface above sibling windows."""

    def activateWindow(self) -> None:
        """Focus the recovery surface."""

    def allow_close(self) -> None:
        """Permit programmatic close after the coordinator handles the action."""

    def close(self) -> bool:
        """Close the recovery surface."""

    def set_retry_callback(self, callback: Callable[[], None]) -> None:
        """Connect the retry action to one callback."""

    def set_force_close_callback(self, callback: Callable[[], None]) -> None:
        """Connect the force-close action to one callback."""

    def show_uncertain_outcome(self, detail_text: str) -> None:
        """Render the uncertain-outcome copy."""

    def show_failed_outcome(self, detail_text: str) -> None:
        """Render the failed-outcome copy."""


ShutdownProgressDialogFactory = Callable[
    [QWidget | None], ShutdownProgressDialogProtocol
]
ShutdownRecoveryDialogFactory = Callable[
    [QWidget | None], ShutdownRecoveryDialogProtocol
]


@dataclass(frozen=True)
class _UnexpectedCleanupFailure:
    """Carry unexpected cleanup task failures back to the UI thread."""

    message: str


class ShutdownCoordinator(QObject):
    """Own coordinated shell shutdown state and background cleanup orchestration."""

    def __init__(
        self,
        *,
        app: AppQuitProtocol,
        cleanup: CleanupFn,
        cleanup_submitter: TaskSubmitter,
        before_cleanup: Callable[[], None] | None = None,
        skip_cleanup_on_force_close: CleanupBypassFn | None = None,
        progress_dialog_factory: ShutdownProgressDialogFactory | None = None,
        recovery_dialog_factory: ShutdownRecoveryDialogFactory | None = None,
    ) -> None:
        """Store shutdown dependencies and prepare UI-thread completion plumbing."""

        super().__init__()
        self._app = app
        self._cleanup = cleanup
        self._cleanup_submitter = cleanup_submitter
        self._cleanup_scope = TaskScope(
            submitter=cleanup_submitter,
            scope_id=f"managed_comfy_shutdown_cleanup_{id(self):x}",
        )
        self._before_cleanup = before_cleanup
        self._skip_cleanup_on_force_close = skip_cleanup_on_force_close
        self._progress_dialog_factory = progress_dialog_factory or (
            lambda parent: ShutdownProgressDialog(parent)
        )
        self._recovery_dialog_factory = recovery_dialog_factory or (
            lambda parent: ShutdownRecoveryDialog(parent)
        )
        self._ui_state = ShutdownUiState.IDLE
        self._active_parent_window: QWidget | None = None
        self._progress_dialog: ShutdownProgressDialogProtocol | None = None
        self._recovery_dialog: ShutdownRecoveryDialogProtocol | None = None
        self._cleanup_handle: TaskHandle[ManagedComfyCleanupResult] | None = None
        self._cleanup_request_ids = count(1)
        self._slow_path_timer = QTimer(self)
        self._slow_path_timer.setSingleShot(True)
        self._slow_path_timer.setInterval(_SLOW_SHUTDOWN_THRESHOLD_MS)
        self._slow_path_timer.timeout.connect(self._show_slow_path_progress)
        self._cleanup_timeout_timer = QTimer(self)
        self._cleanup_timeout_timer.setSingleShot(True)
        self._cleanup_timeout_timer.setInterval(_CLEANUP_ATTEMPT_TIMEOUT_MS)
        self._cleanup_timeout_timer.timeout.connect(self._handle_cleanup_timeout)
        self._cleanup_attempt_timed_out = False

    @property
    def shutdown_in_progress(self) -> bool:
        """Return whether coordinated shutdown is currently active."""

        return self._ui_state in {
            ShutdownUiState.RUNNING_HIDDEN,
            ShutdownUiState.RUNNING_VISIBLE,
            ShutdownUiState.RECOVERY_VISIBLE,
        }

    def request_shutdown(self, parent_window: QWidget | None = None) -> None:
        """Start coordinated shutdown exactly once and ignore duplicate requests."""

        if self._ui_state is not ShutdownUiState.IDLE:
            log_info(
                _LOGGER,
                "Shutdown request ignored because one is already in progress",
                shutdown_ui_state=self._ui_state.value,
            )
            if self._ui_state is ShutdownUiState.FINALIZING_EXIT:
                return
            self._focus_visible_surface()
            return
        self._active_parent_window = parent_window
        self._transition_to(ShutdownUiState.RUNNING_HIDDEN)
        log_info(
            _LOGGER,
            "Shutdown requested",
            shutdown_ui_state=self._ui_state.value,
            shutdown_ui_shown=False,
        )
        self._run_before_cleanup_hook()
        self._slow_path_timer.start()
        self._start_cleanup_task()

    def _run_before_cleanup_hook(self) -> None:
        """Run synchronous UI-thread work before managed cleanup starts."""

        if self._before_cleanup is None:
            return
        try:
            self._before_cleanup()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Pre-cleanup shutdown hook failed; continuing managed cleanup",
                error=error,
            )

    def _start_cleanup_task(self) -> None:
        """Submit one cleanup attempt to the shutdown execution lane."""

        request: TaskRequest[ManagedComfyCleanupResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=next(self._cleanup_request_ids),
                domain="managed_comfy_shutdown_cleanup",
            ),
            context=ExecutionContext(
                operation="managed_comfy_shutdown_cleanup",
                reason="app_shutdown",
                lane="shutdown",
            ),
            work=lambda _token: self._cleanup(),
        )
        self._cleanup_attempt_timed_out = False
        self._cleanup_handle = self._cleanup_scope.submit(request)
        self._cleanup_handle.add_done_callback(
            self._handle_cleanup_task_finished,
            reason="managed_comfy_shutdown_cleanup_finished",
        )
        self._cleanup_timeout_timer.start()
        log_info(
            _LOGGER,
            "Cleanup task submitted",
            shutdown_ui_state=self._ui_state.value,
        )

    def _handle_cleanup_task_finished(
        self,
        outcome: TaskOutcome[ManagedComfyCleanupResult],
    ) -> None:
        """Handle cleanup task completion on the UI thread."""

        self._slow_path_timer.stop()
        self._cleanup_timeout_timer.stop()
        timed_out = self._cleanup_attempt_timed_out
        self._cleanup_attempt_timed_out = False
        self._cleanup_handle = None
        if timed_out:
            log_warning(
                _LOGGER,
                "Late cleanup task result ignored after timeout recovery",
                shutdown_ui_state=self._ui_state.value,
            )
            return
        if outcome.status == "failed":
            error = outcome.error or RuntimeError("Cleanup task failed.")
            log_warning(
                _LOGGER,
                "Cleanup task failed",
                error_type=type(error).__name__,
                shutdown_ui_state=self._ui_state.value,
            )
            self._show_recovery_for_unexpected_failure(
                _UnexpectedCleanupFailure(
                    message=str(error).strip() or type(error).__name__,
                )
            )
            return
        if outcome.status == "cancelled":
            self._show_recovery_for_unexpected_failure(
                _UnexpectedCleanupFailure(
                    message=outcome.cancellation_reason or "Cleanup task cancelled.",
                )
            )
            return
        if not isinstance(outcome.result, ManagedComfyCleanupResult):
            self._show_recovery_for_unexpected_failure(
                _UnexpectedCleanupFailure(
                    message="Shutdown returned an invalid cleanup result."
                )
            )
            return
        result = outcome.result
        log_info(
            _LOGGER,
            "Cleanup task finished",
            pid=result.pid,
            elapsed_ms=result.elapsed_ms,
            cleanup_outcome=result.outcome.value,
        )
        if result.outcome in {
            ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
            ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
        }:
            self._finish_successful_shutdown(result)
            return
        self._show_recovery_dialog(result)

    def _finish_successful_shutdown(self, result: ManagedComfyCleanupResult) -> None:
        """Close shutdown UI and quit the app after successful cleanup."""

        self._transition_to(ShutdownUiState.FINALIZING_EXIT)
        self._cleanup_scope.close(reason="managed_comfy_shutdown_success")
        self._prepare_parent_window_for_close()
        self._close_visible_surfaces()
        log_info(
            _LOGGER,
            "app.quit invoked after successful cleanup",
            pid=result.pid,
            elapsed_ms=result.elapsed_ms,
            cleanup_outcome=result.outcome.value,
            shutdown_ui_shown=result.elapsed_ms >= _SLOW_SHUTDOWN_THRESHOLD_MS,
        )
        self._app.quit()

    def _show_recovery_dialog(self, result: ManagedComfyCleanupResult) -> None:
        """Show the dedicated recovery surface for one non-success result."""

        self._close_progress_dialog()
        dialog = self._ensure_recovery_dialog()
        if result.outcome is ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS:
            dialog.show_uncertain_outcome(result.technical_detail)
        else:
            dialog.show_failed_outcome(result.technical_detail)
        self._transition_to(ShutdownUiState.RECOVERY_VISIBLE)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        log_warning(
            _LOGGER,
            "Recovery dialog shown",
            pid=result.pid,
            elapsed_ms=result.elapsed_ms,
            cleanup_outcome=result.outcome.value,
            verification_timeout=result.verification_timeout,
            taskkill_timeout=result.taskkill_timeout,
            shutdown_ui_state=self._ui_state.value,
            shutdown_ui_shown=True,
            diagnostic_detail=result.diagnostic_detail,
        )

    def _show_recovery_for_unexpected_failure(
        self,
        failure: _UnexpectedCleanupFailure,
    ) -> None:
        """Show the dedicated recovery surface for an unexpected task failure."""

        result = ManagedComfyCleanupResult(
            cleanup_ran=True,
            outcome=ManagedComfyCleanupOutcome.FAILURE,
            managed_resource_present=True,
            live_process_present=False,
            metadata_present=False,
            used_persisted_metadata=False,
            termination_attempted=False,
            registry_cleared=False,
            pid=None,
            host=None,
            port=None,
            workspace=None,
            elapsed_ms=0,
            taskkill_timeout=False,
            verification_timeout=False,
            user_detail="Substitute could not finish closing completely.",
            technical_detail="Shutdown encountered an unexpected error before cleanup could finish.",
            diagnostic_detail=failure.message,
        )
        self._show_recovery_dialog(result)

    def _show_slow_path_progress(self) -> None:
        """Create and show the delayed progress surface after the slow threshold."""

        if self._ui_state is not ShutdownUiState.RUNNING_HIDDEN:
            return
        dialog = self._ensure_progress_dialog()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._transition_to(ShutdownUiState.RUNNING_VISIBLE)
        log_info(
            _LOGGER,
            "Slow-path progress dialog shown",
            shutdown_ui_state=self._ui_state.value,
            shutdown_ui_shown=True,
        )

    def _handle_cleanup_timeout(self) -> None:
        """Show recovery when cleanup fails to finish within the hard timeout."""

        if self._ui_state not in {
            ShutdownUiState.RUNNING_HIDDEN,
            ShutdownUiState.RUNNING_VISIBLE,
        }:
            return
        if self._cleanup_handle is None or self._cleanup_handle.is_finished:
            return
        self._cleanup_attempt_timed_out = True
        result = ManagedComfyCleanupResult(
            cleanup_ran=True,
            outcome=ManagedComfyCleanupOutcome.FAILURE,
            managed_resource_present=True,
            live_process_present=True,
            metadata_present=True,
            used_persisted_metadata=False,
            termination_attempted=True,
            registry_cleared=False,
            pid=None,
            host=None,
            port=None,
            workspace=None,
            elapsed_ms=_CLEANUP_ATTEMPT_TIMEOUT_MS,
            taskkill_timeout=False,
            verification_timeout=True,
            user_detail="Substitute could not finish closing completely.",
            technical_detail="Shutdown timed out before cleanup could finish.",
            diagnostic_detail=(
                "Cleanup task did not finish before the coordinator timeout."
            ),
        )
        log_warning(
            _LOGGER,
            "Cleanup task timed out",
            shutdown_ui_state=self._ui_state.value,
            shutdown_ui_shown=self._ui_state is ShutdownUiState.RUNNING_VISIBLE,
            cleanup_timeout_ms=_CLEANUP_ATTEMPT_TIMEOUT_MS,
        )
        self._show_recovery_dialog(result)

    def _ensure_progress_dialog(self) -> ShutdownProgressDialogProtocol:
        """Create the progress dialog only when the slow path is reached."""

        if self._progress_dialog is None:
            self._progress_dialog = self._progress_dialog_factory(
                self._active_parent_window
            )
        return self._progress_dialog

    def _ensure_recovery_dialog(self) -> ShutdownRecoveryDialogProtocol:
        """Create and wire the recovery dialog the first time it is needed."""

        if self._recovery_dialog is None:
            self._recovery_dialog = self._recovery_dialog_factory(
                self._active_parent_window
            )
            self._recovery_dialog.set_retry_callback(self.retry_shutdown)
            self._recovery_dialog.set_force_close_callback(self.force_close)
        return self._recovery_dialog

    def retry_shutdown(self) -> None:
        """Restart managed cleanup from a clean coordinator state."""

        if self._ui_state is not ShutdownUiState.RECOVERY_VISIBLE:
            return
        if self._cleanup_handle is not None and not self._cleanup_handle.is_finished:
            log_warning(
                _LOGGER,
                "Retry ignored because prior cleanup task is still active",
                shutdown_ui_state=self._ui_state.value,
            )
            self._focus_visible_surface()
            return
        log_info(
            _LOGGER,
            "Retry selected",
            shutdown_ui_state=self._ui_state.value,
        )
        self._close_recovery_dialog()
        self._transition_to(ShutdownUiState.RUNNING_HIDDEN)
        self._slow_path_timer.start()
        self._start_cleanup_task()

    def force_close(self) -> None:
        """Close the app immediately without running another cleanup attempt."""

        if self._ui_state is not ShutdownUiState.RECOVERY_VISIBLE:
            return
        log_warning(
            _LOGGER,
            "Force-close selected",
            shutdown_ui_state=self._ui_state.value,
            force_close_selected=True,
        )
        if self._skip_cleanup_on_force_close is not None:
            self._skip_cleanup_on_force_close()
        self._transition_to(ShutdownUiState.FINALIZING_EXIT)
        self._cleanup_scope.close(reason="managed_comfy_shutdown_force_close")
        self._prepare_parent_window_for_close()
        self._close_visible_surfaces()
        self._app.quit()

    def _focus_visible_surface(self) -> None:
        """Bring the currently visible shutdown surface to the front."""

        dialog = self._recovery_dialog or self._progress_dialog
        if dialog is None:
            return
        try:
            dialog.raise_()
            dialog.activateWindow()
        except RuntimeError as error:
            self._forget_deleted_dialog(dialog, operation="focus", error=error)

    def _prepare_parent_window_for_close(self) -> None:
        """Allow the shell to accept the final Qt close event after shutdown."""

        parent_window = self._active_parent_window
        if parent_window is None:
            return
        allow_direct_close = getattr(parent_window, "allow_direct_close", None)
        if callable(allow_direct_close):
            allow_direct_close()

    def _close_visible_surfaces(self) -> None:
        """Close any visible shutdown UI before the app exits or retries."""

        self._close_progress_dialog()
        self._close_recovery_dialog()
        self._active_parent_window = None

    def _close_progress_dialog(self) -> None:
        """Close and forget the delayed progress dialog when it exists."""

        dialog = self._progress_dialog
        if dialog is None:
            return
        try:
            dialog.allow_close()
            dialog.close()
        except RuntimeError as error:
            self._forget_deleted_dialog(dialog, operation="close_progress", error=error)
        self._progress_dialog = None

    def _close_recovery_dialog(self) -> None:
        """Close and forget the recovery dialog when it exists."""

        dialog = self._recovery_dialog
        if dialog is None:
            return
        try:
            dialog.allow_close()
            dialog.close()
        except RuntimeError as error:
            self._forget_deleted_dialog(dialog, operation="close_recovery", error=error)
        self._recovery_dialog = None

    def _forget_deleted_dialog(
        self,
        dialog: object,
        *,
        operation: str,
        error: RuntimeError,
    ) -> None:
        """Drop stale Qt dialog wrappers after their C++ object has been deleted."""

        if dialog is self._progress_dialog:
            self._progress_dialog = None
        if dialog is self._recovery_dialog:
            self._recovery_dialog = None
        log_warning(
            _LOGGER,
            "Ignored stale shutdown dialog wrapper",
            operation=operation,
            error=error,
            shutdown_ui_state=self._ui_state.value,
        )

    def _transition_to(self, state: ShutdownUiState) -> None:
        """Record one explicit coordinator UI-state transition."""

        self._ui_state = state
