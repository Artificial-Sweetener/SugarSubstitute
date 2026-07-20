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

"""Centralize startup signal wiring and shutdown cleanup behavior."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import signal
import sys
import threading
from time import monotonic
from typing import Callable

from PySide6.QtWidgets import QApplication

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.infrastructure.comfy.managed_shutdown import (
    ManagedProcessTerminationStatus,
)
from substitute.infrastructure.comfy.process_manager import (
    ManagedComfyState,
    ManagedComfyStateCleanupResult,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.lifecycle")

KillProcessFn = Callable[[ManagedComfyState | None], ManagedComfyStateCleanupResult]
ManagedComfyStateGetter = Callable[[], ManagedComfyState | None]


class ManagedComfyCleanupOutcome(Enum):
    """Describe the lifecycle-level outcome of one cleanup attempt."""

    NO_ACTION_REQUIRED = "no_action_required"
    CONFIRMED_SUCCESS = "confirmed_success"
    UNCERTAIN_SUCCESS = "uncertain_success"
    FAILURE = "failure"


@dataclass(frozen=True)
class ManagedComfyCleanupResult:
    """Describe one lifecycle-level managed ComfyUI cleanup attempt."""

    cleanup_ran: bool
    outcome: ManagedComfyCleanupOutcome
    managed_resource_present: bool
    live_process_present: bool
    metadata_present: bool
    used_persisted_metadata: bool
    termination_attempted: bool
    registry_cleared: bool
    pid: int | None
    host: str | None
    port: int | None
    workspace: Path | None
    elapsed_ms: int
    taskkill_timeout: bool
    verification_timeout: bool
    user_detail: ApplicationText
    technical_detail: ApplicationText
    diagnostic_detail: str


CleanupFn = Callable[[], ManagedComfyCleanupResult]
CleanupBypassFn = Callable[[], None]


class ManagedComfyCleanupHandler:
    """Provide retryable managed-Comfy cleanup with explicit force-close bypass."""

    def __init__(
        self,
        comfy_state_getter: ManagedComfyStateGetter,
        kill_process: KillProcessFn,
    ) -> None:
        """Store cleanup dependencies and initialize lifecycle state."""

        self._comfy_state_getter = comfy_state_getter
        self._kill_process = kill_process
        self._lock = threading.Lock()
        self._cached_terminal_result: ManagedComfyCleanupResult | None = None
        self._skip_future_cleanup = False
        self._skip_result: ManagedComfyCleanupResult | None = None

    def __call__(self) -> ManagedComfyCleanupResult:
        """Run managed cleanup once per successful app exit, but allow retries."""

        with self._lock:
            if self._cached_terminal_result is not None:
                return self._cached_terminal_result
            if self._skip_future_cleanup:
                assert self._skip_result is not None
                return self._skip_result
        result = self._run_cleanup_attempt()
        with self._lock:
            if result.outcome in {
                ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
                ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
            }:
                self._cached_terminal_result = result
        return result

    def skip_future_cleanup(self) -> None:
        """Bypass future cleanup hooks after the user chooses force-close."""

        with self._lock:
            self._skip_future_cleanup = True
            self._skip_result = ManagedComfyCleanupResult(
                cleanup_ran=False,
                outcome=ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
                managed_resource_present=False,
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
                user_detail=app_text(
                    "Cleanup was skipped because force-close was selected."
                ),
                technical_detail=app_text(
                    "Cleanup skipped after force-close selection."
                ),
                diagnostic_detail="Coordinator bypassed cleanup after force-close selection.",
            )
        log_info(_LOGGER, "Future cleanup skipped after force-close selection")

    def _run_cleanup_attempt(self) -> ManagedComfyCleanupResult:
        """Execute one cleanup attempt and translate it into lifecycle terms."""

        started_at = monotonic()
        comfy_state = self._comfy_state_getter()
        if comfy_state is None:
            return ManagedComfyCleanupResult(
                cleanup_ran=True,
                outcome=ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
                managed_resource_present=False,
                live_process_present=False,
                metadata_present=False,
                used_persisted_metadata=False,
                termination_attempted=False,
                registry_cleared=False,
                pid=None,
                host=None,
                port=None,
                workspace=None,
                elapsed_ms=_elapsed_ms_since(started_at),
                taskkill_timeout=False,
                verification_timeout=False,
                user_detail=app_text("No managed ComfyUI cleanup was required."),
                technical_detail=app_text("No managed ComfyUI cleanup was required."),
                diagnostic_detail="Managed ComfyUI state was unavailable during cleanup.",
            )
        metadata = comfy_state.metadata
        process = comfy_state.proc
        pid = (
            process.pid
            if process is not None
            else (metadata.pid if metadata is not None else None)
        )
        host = metadata.host if metadata is not None else None
        port = metadata.port if metadata is not None else None
        workspace = metadata.workspace_path if metadata is not None else None
        log_info(
            _LOGGER,
            "Managed ComfyUI cleanup started",
            pid=pid,
            host=host,
            port=port,
            workspace=str(workspace) if workspace is not None else None,
            live_process_handle=process is not None and process.poll() is None,
            used_persisted_metadata=process is None and metadata is not None,
        )
        try:
            comfy_state.request_stop(reason="managed_comfy_cleanup")

            def cleanup_after_spawn() -> ManagedComfyStateCleanupResult:
                """Terminate the managed state after process spawning settles."""

                process = comfy_state.proc
                if process is not None:
                    log_info(_LOGGER, "Cleanup terminating ComfyUI", pid=process.pid)
                elif comfy_state.metadata is not None:
                    log_info(
                        _LOGGER,
                        "Cleanup terminating owned ComfyUI",
                        pid=comfy_state.metadata.pid,
                    )
                return self._kill_process(comfy_state)

            state_cleanup = comfy_state.with_spawn_lock(cleanup_after_spawn)
        except Exception:
            result = ManagedComfyCleanupResult(
                cleanup_ran=True,
                outcome=ManagedComfyCleanupOutcome.FAILURE,
                managed_resource_present=True,
                live_process_present=process is not None and process.poll() is None,
                metadata_present=metadata is not None,
                used_persisted_metadata=process is None and metadata is not None,
                termination_attempted=False,
                registry_cleared=False,
                pid=pid,
                host=host,
                port=port,
                workspace=workspace,
                elapsed_ms=_elapsed_ms_since(started_at),
                taskkill_timeout=False,
                verification_timeout=False,
                user_detail=app_text("Substitute could not finish closing completely."),
                technical_detail=app_text(
                    "Shutdown encountered an unexpected error before cleanup could finish."
                ),
                diagnostic_detail=(
                    "Cleanup encountered an unexpected error before termination could be verified."
                ),
            )
            log_exception(
                _LOGGER,
                "Cleanup encountered an unexpected error",
                pid=pid,
                host=host,
                port=port,
                workspace=str(workspace) if workspace is not None else None,
                elapsed_ms=result.elapsed_ms,
                cleanup_outcome=result.outcome.value,
            )
            return result
        result = _build_cleanup_result(
            state_cleanup=state_cleanup,
            elapsed_ms=_elapsed_ms_since(started_at),
        )
        log_method = (
            log_info
            if result.outcome
            in {
                ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
                ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
            }
            else log_warning
        )
        log_method(
            _LOGGER,
            "Managed ComfyUI cleanup finished",
            pid=result.pid,
            host=result.host,
            port=result.port,
            workspace=str(result.workspace) if result.workspace is not None else None,
            elapsed_ms=result.elapsed_ms,
            termination_attempted=result.termination_attempted,
            cleanup_outcome=result.outcome.value,
            taskkill_timeout=result.taskkill_timeout,
            verification_timeout=result.verification_timeout,
            diagnostic_detail=result.diagnostic_detail,
        )
        return result


def register_signal_handlers() -> None:
    """Map SIGINT/SIGTERM to immediate process exit semantics."""

    signal.signal(signal.SIGINT, lambda _signum, _frame: sys.exit(1))
    signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(1))


def create_cleanup_handler(
    comfy_state_getter: ManagedComfyStateGetter,
    kill_process: KillProcessFn,
) -> ManagedComfyCleanupHandler:
    """Build a retryable shutdown handler for managed ComfyUI state."""

    return ManagedComfyCleanupHandler(comfy_state_getter, kill_process)


def register_shutdown_handlers(app: QApplication, cleanup: CleanupFn) -> None:
    """Attach cleanup to Qt shutdown and Python process exit."""

    try:
        app.aboutToQuit.connect(cleanup)
    except Exception:
        log_warning(_LOGGER, "Failed to connect aboutToQuit cleanup hook")
    atexit.register(cleanup)


def _build_cleanup_result(
    *,
    state_cleanup: ManagedComfyStateCleanupResult,
    elapsed_ms: int,
) -> ManagedComfyCleanupResult:
    """Translate one process-manager cleanup result into lifecycle terms."""

    outcome = _map_cleanup_outcome(state_cleanup)
    technical_detail = _build_technical_detail(state_cleanup, outcome)
    user_detail = _build_user_detail(outcome)
    termination = state_cleanup.termination
    return ManagedComfyCleanupResult(
        cleanup_ran=True,
        outcome=outcome,
        managed_resource_present=state_cleanup.managed_resource_present,
        live_process_present=state_cleanup.live_process_present,
        metadata_present=state_cleanup.metadata_present,
        used_persisted_metadata=state_cleanup.used_persisted_metadata,
        termination_attempted=state_cleanup.termination_attempted,
        registry_cleared=state_cleanup.registry_cleared,
        pid=state_cleanup.pid,
        host=state_cleanup.host,
        port=state_cleanup.port,
        workspace=state_cleanup.workspace,
        elapsed_ms=elapsed_ms,
        taskkill_timeout=(
            termination.termination_command_timed_out
            if termination is not None
            else False
        ),
        verification_timeout=(
            termination.verification_timed_out if termination is not None else False
        ),
        user_detail=user_detail,
        technical_detail=technical_detail,
        diagnostic_detail=state_cleanup.diagnostic_detail,
    )


def _map_cleanup_outcome(
    state_cleanup: ManagedComfyStateCleanupResult,
) -> ManagedComfyCleanupOutcome:
    """Map normalized termination facts into lifecycle cleanup outcomes."""

    if not state_cleanup.managed_resource_present:
        return ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED
    status = state_cleanup.termination_status
    if status is ManagedProcessTerminationStatus.TERMINATED_CONFIRMED:
        return ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS
    if status is ManagedProcessTerminationStatus.TERMINATION_UNCONFIRMED:
        return ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS
    return ManagedComfyCleanupOutcome.FAILURE


def _build_user_detail(outcome: ManagedComfyCleanupOutcome) -> ApplicationText:
    """Build the primary user-facing summary for one cleanup outcome."""

    if outcome is ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED:
        return app_text("No managed ComfyUI cleanup was required.")
    if outcome is ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS:
        return app_text("Substitute finished closing cleanly.")
    if outcome is ManagedComfyCleanupOutcome.UNCERTAIN_SUCCESS:
        return app_text("Substitute could not confirm that shutdown finished.")
    return app_text("Substitute could not finish closing completely.")


def _build_technical_detail(
    state_cleanup: ManagedComfyStateCleanupResult,
    outcome: ManagedComfyCleanupOutcome,
) -> ApplicationText:
    """Build one sanitized technical detail string for optional user display."""

    if outcome in {
        ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
    }:
        return state_cleanup.user_safe_detail
    termination = state_cleanup.termination
    if termination is None:
        return app_text("Shutdown could not finish.")
    return termination.user_safe_detail


def _elapsed_ms_since(started_at: float) -> int:
    """Return elapsed whole milliseconds since one monotonic start timestamp."""

    return int((monotonic() - started_at) * 1000)


__all__ = [
    "CleanupBypassFn",
    "CleanupFn",
    "KillProcessFn",
    "ManagedComfyCleanupHandler",
    "ManagedComfyCleanupOutcome",
    "ManagedComfyCleanupResult",
    "ManagedComfyStateGetter",
    "create_cleanup_handler",
    "register_shutdown_handlers",
    "register_signal_handlers",
]
