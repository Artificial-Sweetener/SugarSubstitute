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

"""Own the splash-to-shell handoff during approved nodepack recovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from sugarsubstitute_shared.launch_splash.activity import SplashActivity
from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("app.bootstrap.nodepack_recovery_handoff")


class NodepackShellSurface(Protocol):
    """Expose the old shell's visibility without owning its disposal."""

    def hide(self) -> None:
        """Hide the shell while the recovery splash is active."""

    def show(self) -> None:
        """Restore the shell after a recoverable failure."""


class NodepackSplashSurface(Protocol):
    """Expose the launch splash's bounded recovery presentation contract."""

    def set_cancellation_enabled(self, enabled: bool) -> None:
        """Prevent a close gesture from abandoning an active installation."""

    def center_on_screen(self) -> None:
        """Position the splash before revealing it."""

    def append_log(self, line: str) -> None:
        """Publish one localized recovery stage."""

    def start_activity(self, activity: SplashActivity) -> None:
        """Animate the current stage on the splash and terminal tail."""

    def show(self) -> None:
        """Reveal the recovery splash."""

    def dismiss(self) -> None:
        """Close the splash without emitting a cancellation request."""

    def deleteLater(self) -> None:
        """Release the Qt presentation surface after the current event."""


class NodepackRecoveryHandoff:
    """Keep one old shell recoverable until fresh Comfy metadata permits reload."""

    def __init__(
        self,
        *,
        current_shell: Callable[[], NodepackShellSurface | None],
        has_cancellable_jobs: Callable[[], bool],
        create_splash: Callable[[], NodepackSplashSurface],
        reload_gui: Callable[[], bool],
    ) -> None:
        """Store application-lifetime ports outside the disposable shell."""

        self._current_shell = current_shell
        self._has_cancellable_jobs = has_cancellable_jobs
        self._create_splash = create_splash
        self._reload_gui = reload_gui
        self._old_shell: NodepackShellSurface | None = None
        self._splash: NodepackSplashSurface | None = None
        self._stage_text: str | None = None

    def begin(self) -> bool:
        """Show the splash only when the shell and generation queue are safe."""

        if self._splash is not None:
            return False
        try:
            if self._has_cancellable_jobs():
                return False
            shell = self._current_shell()
        except Exception as error:
            log_exception(
                _LOGGER,
                "Could not assess nodepack recovery handoff safety",
                error=error,
            )
            return False
        if shell is None:
            return False
        splash: NodepackSplashSurface | None = None
        try:
            splash = self._create_splash()
            splash.set_cancellation_enabled(False)
            self._stage_text = _announce(
                splash,
                app_text("Installing required custom nodes"),
                previous=None,
            )
            splash.center_on_screen()
            splash.show()
            shell.hide()
        except Exception as error:
            log_exception(
                _LOGGER, "Could not begin nodepack recovery handoff", error=error
            )
            if splash is not None:
                splash.dismiss()
                splash.deleteLater()
            self._stage_text = None
            shell.show()
            return False
        self._old_shell = shell
        self._splash = splash
        log_info(_LOGGER, "Nodepack recovery splash replaced the shell")
        return True

    def report(self, message: ApplicationText) -> None:
        """Publish a localized recovery stage while the splash is alive."""

        if self._splash is not None:
            self._stage_text = _announce(
                self._splash,
                message,
                previous=self._stage_text,
            )

    def reload(self) -> bool:
        """Request the session-saving GUI reload after Comfy verification."""

        if self._splash is None:
            return False
        self.report(app_text("Preparing your saved workspace."))
        if self._reload_gui():
            return True
        self.cancel()
        return False

    def finish(self) -> None:
        """Dismiss the splash immediately before the replacement shell appears."""

        self._close_splash()
        self._old_shell = None

    def cancel(self) -> None:
        """Return to the preserved old shell after a recoverable failure."""

        old_shell = self._old_shell
        if self._splash is None and old_shell is None:
            return
        self._close_splash()
        self._old_shell = None
        if old_shell is not None and self._current_shell() is old_shell:
            old_shell.show()
        log_info(_LOGGER, "Nodepack recovery handoff returned to the shell")

    def _close_splash(self) -> None:
        """Release one splash without changing the old shell's visibility."""

        splash = self._splash
        self._splash = None
        self._stage_text = None
        if splash is not None:
            splash.dismiss()
            splash.deleteLater()


def _announce(
    splash: NodepackSplashSurface,
    message: ApplicationText,
    *,
    previous: str | None,
) -> str:
    """Retain completed stages while reserving the animated row for current work."""

    rendered = render_application_text(message)
    if previous is not None and previous != rendered:
        splash.append_log(previous)
    splash.start_activity(
        SplashActivity(
            initial_text=rendered,
            long_wait_text=render_application_text(
                app_text("%1…\nThis is taking longer than usual", rendered)
            ),
            extended_wait_text=render_application_text(
                app_text("%1…\nThis is taking much longer than expected", rendered)
            ),
        )
    )
    return rendered


__all__ = [
    "NodepackRecoveryHandoff",
    "NodepackShellSurface",
    "NodepackSplashSurface",
]
