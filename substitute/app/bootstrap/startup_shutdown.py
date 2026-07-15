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

"""Own startup shutdown, managed-Comfy leases, and relaunch decisions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from threading import Lock
from types import TracebackType
from typing import Any, cast

from substitute.app.bootstrap import lifecycle
from substitute.app.bootstrap.lifecycle import (
    CleanupFn,
    KillProcessFn,
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
    ManagedComfyStateGetter,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("app.bootstrap.startup_shutdown")


class ManagedComfyLeaseError(RuntimeError):
    """Report invalid managed-Comfy lease state transitions."""


@dataclass(frozen=True, slots=True)
class GuiReloadLease:
    """Represent one sanctioned GUI reload transaction."""

    _owner: ManagedComfyLease
    _token: int

    def __enter__(self) -> GuiReloadLease:
        """Return this active reload transaction for context-manager use."""

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """End the sanctioned GUI reload transaction."""

        del exc_type, exc_value, traceback
        self.close()

    def close(self) -> None:
        """Release the sanctioned GUI reload transaction exactly once."""

        self._owner._end_gui_reload(self._token)


class ManagedComfyLease:
    """Own the process-level obligation to terminate managed ComfyUI."""

    def __init__(self, cleanup: CleanupFn) -> None:
        """Store the cleanup handler guarded by this lease."""

        self._cleanup = cleanup
        self._lock = Lock()
        self._active_reload_token: int | None = None
        self._next_reload_token = 1
        self._cleanup_finished = False

    @property
    def gui_reload_active(self) -> bool:
        """Return whether a sanctioned GUI reload transaction is active."""

        with self._lock:
            return self._active_reload_token is not None

    @property
    def cleanup_finished(self) -> bool:
        """Return whether managed cleanup has reached a terminal success state."""

        with self._lock:
            return self._cleanup_finished

    def begin_gui_reload(self) -> GuiReloadLease:
        """Enter the only sanctioned shell-disposal path that keeps ComfyUI alive."""

        with self._lock:
            if self._cleanup_finished:
                raise ManagedComfyLeaseError(
                    "GUI reload cannot start after managed ComfyUI cleanup finished."
                )
            if self._active_reload_token is not None:
                raise ManagedComfyLeaseError("GUI reload is already active.")
            token = self._next_reload_token
            self._next_reload_token += 1
            self._active_reload_token = token
        log_info(_LOGGER, "Managed ComfyUI GUI reload lease started", token=token)
        return GuiReloadLease(_owner=self, _token=token)

    def cleanup(self) -> ManagedComfyCleanupResult:
        """Terminate owned managed ComfyUI through the guarded cleanup handler."""

        result = self._cleanup()
        if cleanup_result_allows_terminal_lease_close(result):
            with self._lock:
                self._cleanup_finished = True
        log_info(
            _LOGGER,
            "Managed ComfyUI lease cleanup returned",
            cleanup_outcome=result.outcome.value,
            cleanup_finished=self.cleanup_finished,
            gui_reload_active=self.gui_reload_active,
            pid=result.pid,
        )
        return result

    def _end_gui_reload(self, token: int) -> None:
        """Leave one sanctioned GUI reload transaction."""

        with self._lock:
            if self._active_reload_token != token:
                return
            self._active_reload_token = None
        log_info(_LOGGER, "Managed ComfyUI GUI reload lease ended", token=token)


class StartupShutdownRuntime:
    """Coordinate managed cleanup state for one startup process lifetime."""

    def __init__(
        self,
        *,
        cleanup_handler: CleanupFn,
        save_session_before_cleanup: Callable[[], None] | None = None,
    ) -> None:
        """Store shutdown collaborators and initialize managed cleanup state."""

        self._cleanup_handler = cleanup_handler
        self._save_session_before_cleanup = save_session_before_cleanup
        self._managed_comfy_lease = ManagedComfyLease(cleanup_handler)
        self._last_cleanup_result: ManagedComfyCleanupResult | None = None

    @property
    def managed_comfy_lease(self) -> ManagedComfyLease:
        """Return the managed-Comfy lease shared with GUI reload coordination."""

        return self._managed_comfy_lease

    @property
    def cleanup_bypass(self) -> Callable[[], None] | None:
        """Return the force-close cleanup bypass hook when the handler exposes one."""

        skip_cleanup = getattr(self._cleanup_handler, "skip_future_cleanup", None)
        return skip_cleanup if callable(skip_cleanup) else None

    @property
    def last_cleanup_result(self) -> ManagedComfyCleanupResult | None:
        """Return the latest managed cleanup result observed by startup shutdown."""

        return self._last_cleanup_result

    def save_session_before_cleanup(self) -> None:
        """Persist the live shell session before managed Comfy cleanup starts."""

        if self._save_session_before_cleanup is not None:
            self._save_session_before_cleanup()

    def cleanup(self) -> ManagedComfyCleanupResult:
        """Run managed cleanup through the lease and remember its result."""

        result = self._managed_comfy_lease.cleanup()
        self._last_cleanup_result = result
        return result

    def register_shutdown_handlers(self, app: object) -> None:
        """Attach managed cleanup to Qt shutdown and Python process exit."""

        lifecycle.register_shutdown_handlers(cast(Any, app), self.cleanup)

    def relaunch_after_cleanup_if_requested(
        self,
        *,
        restart_requested: bool,
        restart_launch_command: Sequence[str],
        start_ready_app_process: Callable[[Sequence[str]], bool],
    ) -> None:
        """Relaunch the ready app only after a requested successful cleanup."""

        if not restart_requested:
            return
        if cleanup_result_allows_relaunch(self._last_cleanup_result):
            start_ready_app_process(restart_launch_command)
            return
        log_warning(
            _LOGGER,
            "Skipped ComfyUI restart relaunch after unsuccessful cleanup",
            cleanup_result_present=self._last_cleanup_result is not None,
            cleanup_ran=False
            if self._last_cleanup_result is None
            else self._last_cleanup_result.cleanup_ran,
            cleanup_outcome=""
            if self._last_cleanup_result is None
            else self._last_cleanup_result.outcome.value,
        )


def create_startup_shutdown_runtime(
    *,
    comfy_state_getter: ManagedComfyStateGetter,
    kill_process: KillProcessFn,
    save_session_before_cleanup: Callable[[], None] | None = None,
) -> StartupShutdownRuntime:
    """Build startup shutdown runtime state around managed Comfy cleanup."""

    cleanup_handler = lifecycle.create_cleanup_handler(comfy_state_getter, kill_process)
    return StartupShutdownRuntime(
        cleanup_handler=cleanup_handler,
        save_session_before_cleanup=save_session_before_cleanup,
    )


def cleanup_result_allows_terminal_lease_close(
    result: ManagedComfyCleanupResult,
) -> bool:
    """Return whether cleanup reached a terminal state for the process lease."""

    return result.outcome in {
        ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        ManagedComfyCleanupOutcome.CONFIRMED_SUCCESS,
    }


def cleanup_result_allows_relaunch(
    result: ManagedComfyCleanupResult | None,
) -> bool:
    """Return whether cleanup reached a state safe for launching a replacement app."""

    if result is None or not result.cleanup_ran:
        return False
    return cleanup_result_allows_terminal_lease_close(result)


__all__ = [
    "GuiReloadLease",
    "ManagedComfyLease",
    "ManagedComfyLeaseError",
    "StartupShutdownRuntime",
    "cleanup_result_allows_relaunch",
    "cleanup_result_allows_terminal_lease_close",
    "create_startup_shutdown_runtime",
]
