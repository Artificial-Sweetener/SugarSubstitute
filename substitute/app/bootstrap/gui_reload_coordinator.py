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

"""Coordinate full GUI reload while preserving managed ComfyUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.app.bootstrap.gui_reload_session_finalizer import (
    GuiReloadFinalizationStart,
    GuiReloadSessionFinalizer,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.gui_reload_coordinator")
ReloadMessageSink = Callable[[str], None]


class ShellFrameProtocol(Protocol):
    """Describe shell-frame lifecycle methods used during GUI reload."""

    def allow_direct_close(self) -> None:
        """Allow sanctioned shell disposal without coordinated shutdown."""

    def suppress_app_quit_on_close(self) -> None:
        """Prevent frame disposal from quitting the application."""

    def hide(self) -> None:
        """Hide the shell frame."""

    def close(self) -> object:
        """Close the shell frame."""

    def deleteLater(self) -> None:
        """Schedule shell-frame deletion after the current Qt event returns."""


class GuiReloadCoordinator:
    """Reload the shell while preserving the managed ComfyUI lease."""

    def __init__(
        self,
        *,
        current_shell: Callable[[], ShellFrameProtocol | None],
        set_current_shell: Callable[[ShellFrameProtocol | None], None],
        main_window_for_shell: Callable[[ShellFrameProtocol], object | None],
        build_shell: Callable[[], ShellFrameProtocol],
        show_shell: Callable[[ShellFrameProtocol], ShellFrameProtocol],
        hydrate_shell: Callable[[ShellFrameProtocol], None],
        session_finalizer: GuiReloadSessionFinalizer,
        request_shutdown: Callable[[ShellFrameProtocol | None], None],
        has_cancellable_jobs: Callable[[], bool],
        message_sink: ReloadMessageSink | None = None,
    ) -> None:
        """Store the transaction collaborators for full shell rebuild."""

        self._current_shell = current_shell
        self._set_current_shell = set_current_shell
        self._main_window_for_shell = main_window_for_shell
        self._build_shell = build_shell
        self._show_shell = show_shell
        self._hydrate_shell = hydrate_shell
        self._session_finalizer = session_finalizer
        self._request_shutdown = request_shutdown
        self._has_cancellable_jobs = has_cancellable_jobs
        self._message_sink = message_sink

    def reload_shell(self) -> bool:
        """Capture, dispose, rebuild, and materialize the shell transactionally."""

        old_shell = self._current_shell()
        has_cancellable_jobs = self._has_cancellable_jobs()
        log_info(
            _LOGGER,
            "gui reload entry",
            old_shell_present=old_shell is not None,
            cleanup_finished=self._session_finalizer.cleanup_finished,
            has_cancellable_jobs=has_cancellable_jobs,
        )
        if old_shell is None:
            log_warning(_LOGGER, "GUI reload rejected because no shell is active")
            self._show_message("Substitute cannot reload the GUI before it is open.")
            return False
        if has_cancellable_jobs:
            log_warning(_LOGGER, "GUI reload rejected while generation jobs are active")
            self._show_message(
                "Wait for the generation queue to finish before reloading the GUI."
            )
            return False
        if self._session_finalizer.cleanup_finished:
            log_warning(
                _LOGGER,
                "GUI reload rejected because managed ComfyUI cleanup is finished",
            )
            self._show_message("Substitute cannot reload the GUI while closing.")
            return False
        main_window = self._main_window_for_shell(old_shell)
        log_info(
            _LOGGER,
            "gui reload resolved main window",
            main_window_present=main_window is not None,
            main_window_type=type(main_window).__name__
            if main_window is not None
            else "",
        )
        if main_window is None:
            log_warning(_LOGGER, "GUI reload rejected because shell has no MainWindow")
            self._show_message("Substitute cannot reload this GUI shell.")
            return False
        finalization_start = self._session_finalizer.begin(
            main_window,
            on_success=lambda: self._reload_after_finalization(
                old_shell,
                main_window,
            ),
            on_failure=self._session_finalization_failed,
        )
        if finalization_start is GuiReloadFinalizationStart.ACCEPTED:
            return True
        if finalization_start is GuiReloadFinalizationStart.LEASE_CLOSED:
            log_warning(
                _LOGGER,
                "GUI reload rejected because managed ComfyUI lease is closed",
            )
            self._show_message("Substitute cannot reload the GUI while closing.")
        elif finalization_start is GuiReloadFinalizationStart.PREPARATION_FAILED:
            self._show_message("Substitute could not save the current session.")
        return False

    def _session_finalization_failed(self) -> None:
        """Report that durable session finalization blocked GUI reload."""

        self._show_message("Substitute could not save the current session.")

    def _reload_after_finalization(
        self,
        old_shell: ShellFrameProtocol,
        main_window: object,
    ) -> None:
        """Dispose and rebuild one shell after durable session finalization."""

        log_info(_LOGGER, "gui reload lease entered")
        try:
            self._detach_old_shell(main_window)
        except Exception as error:
            log_exception(
                _LOGGER,
                "GUI reload could not release old shell resources; failing closed",
                error=error,
            )
            self._show_message(
                "Substitute could not release the current GUI and will close safely."
            )
            self._request_shutdown(old_shell)
            return
        self._dispose_old_shell(old_shell)
        try:
            log_info(_LOGGER, "gui reload building new shell")
            new_shell = self._build_shell()
            log_info(
                _LOGGER,
                "gui reload built new shell",
                new_shell_type=type(new_shell).__name__,
            )
            self._set_current_shell(new_shell)
            log_info(_LOGGER, "gui reload hydrating new shell")
            self._hydrate_shell(new_shell)
            log_info(_LOGGER, "gui reload showing new shell")
            shown_shell = self._show_shell(new_shell)
            self._set_current_shell(shown_shell)
        except Exception as error:
            log_exception(
                _LOGGER,
                "GUI reload failed after old shell disposal; failing closed",
                error=error,
            )
            self._show_message(
                "Substitute could not reload the GUI and will close safely."
            )
            self._request_shutdown(self._current_shell())
            return
        log_info(_LOGGER, "GUI reload completed")

    def _dispose_old_shell(self, shell: ShellFrameProtocol) -> None:
        """Dispose the old shell without requesting full application quit."""

        shell.suppress_app_quit_on_close()
        shell.allow_direct_close()
        log_info(
            _LOGGER,
            "gui reload disposing old shell",
            shell_type=type(shell).__name__,
        )
        self._set_current_shell(None)
        shell.hide()
        shell.close()
        shell.deleteLater()
        log_info(_LOGGER, "Disposed old GUI shell during reload")

    def _detach_old_shell(self, main_window: object) -> None:
        """Detach shell observers before widget disposal."""

        reload_lifecycle_controller = getattr(
            main_window,
            "shell_reload_lifecycle_controller",
            None,
        )
        detach = getattr(reload_lifecycle_controller, "detach_for_gui_reload", None)
        if callable(detach):
            detach()
        log_info(_LOGGER, "Detached old GUI shell observers during reload")

    def _show_message(self, message: str) -> None:
        """Show one user-visible reload message when a sink exists."""

        if self._message_sink is not None:
            self._message_sink(message)


__all__ = [
    "GuiReloadCoordinator",
    "ReloadMessageSink",
    "ShellFrameProtocol",
]
