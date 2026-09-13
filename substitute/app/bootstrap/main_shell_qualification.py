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

"""Drive a normal main-shell close for authenticated installer qualification."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QWidget

from substitute.shared.logging.logger import get_logger, log_exception, log_info
from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan


_LOGGER = get_logger("app.bootstrap.main_shell_qualification")
_POLL_INTERVAL_MILLISECONDS = 50


class MainShellQualificationDriver(QObject):
    """Wait for CI verification before closing the real application surface."""

    def __init__(self, *, window: QWidget, plan: InstallerQualificationPlan) -> None:
        """Bind one authenticated plan to its visible main-shell window."""

        super().__init__(window)
        self._window = window
        self._plan = plan
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MILLISECONDS)
        self._timer.timeout.connect(self._poll_shutdown_request)

    def start(self) -> None:
        """Begin waiting for the verifier's explicit normal-close request."""

        self._timer.start()

    def _poll_shutdown_request(self) -> None:
        """Close the production window after consuming this run's request."""

        try:
            requested = self._plan.consume_main_shell_shutdown_request()
        except (OSError, ValueError):
            self._timer.stop()
            log_exception(
                _LOGGER,
                "Rejected invalid installer qualification shutdown request",
            )
            return
        if not requested:
            return
        self._timer.stop()
        self._plan.record("main_shell.shutdown.requested")
        log_info(_LOGGER, "Installer qualification requested normal shell shutdown")
        self._window.close()


def schedule_main_shell_qualification(window: object) -> bool:
    """Start clean-exit qualification only for an inherited explicit plan."""

    plan = InstallerQualificationPlan.from_environment()
    if plan is None or not isinstance(window, QWidget):
        return False
    driver = MainShellQualificationDriver(window=window, plan=plan)
    driver.start()
    return True


__all__ = ["MainShellQualificationDriver", "schedule_main_shell_qualification"]
