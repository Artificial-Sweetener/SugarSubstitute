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

"""Own installer close requests across active transactional worker stages."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QWidget

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.installation_execution import (
    QtInstallationExecutor,
)
from launcher.sugarsubstitute_launcher.ui.installer_view import InstallerView
from launcher.sugarsubstitute_launcher.ui.repair_preparation_execution import (
    QtRepairPreparationExecutor,
)


_LOGGER = logging.getLogger(__name__)


class InstallationCloseCoordinator(QObject):
    """Defer window destruction until every owned worker reaches a safe boundary."""

    def __init__(
        self,
        *,
        window: QWidget,
        view: InstallerView,
        installation: QtInstallationExecutor,
        repair: QtRepairPreparationExecutor,
        handoff_completed: Callable[[], None],
    ) -> None:
        """Bind the window, its worker owners, and visible progress surface."""

        super().__init__(window)
        self._window = window
        self._view = view
        self._installation = installation
        self._repair = repair
        self._close_requested = False
        self._handoff_requested = False
        self._handoff_completed = handoff_completed
        window.installEventFilter(self)

    @property
    def close_requested(self) -> bool:
        """Return whether closure is waiting for an active safe boundary."""

        return self._close_requested

    def finish_if_safe(self) -> bool:
        """Schedule the requested close after the final worker releases ownership."""

        if self._has_active_work() or not (
            self._close_requested or self._handoff_requested
        ):
            return False
        self._close_requested = False
        if self._handoff_requested:
            self._handoff_requested = False
            self._handoff_completed()
        _LOGGER.info("Installer reached its requested safe close boundary")
        QTimer.singleShot(0, self._window.close)
        return True

    def request_handoff(self) -> None:
        """Hide completed setup and defer process exit until its workers finish."""
        self._handoff_requested = True
        self._window.hide()
        self.finish_if_safe()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercept close only while this exact window still owns worker work."""

        if (
            watched is self._window
            and event.type() is QEvent.Type.Close
            and self._has_active_work()
        ):
            self._defer_close()
            if isinstance(event, QCloseEvent):
                event.ignore()
            return True
        return super().eventFilter(watched, event)

    def _defer_close(self) -> None:
        """Stop after the active step and explain why the window remains visible."""

        if self._close_requested:
            return
        self._close_requested = True
        self._installation.request_stop_after_current_stage()
        message = launcher_text("Finishing the current setup step before closing.")
        if self._repair.running:
            self._view.repair_page.set_status(message, working=True)
        else:
            self._view.show_status_output()
            self._view.append_log(message)
        _LOGGER.info(
            "Installer close deferred to a safe boundary | initial_running=%s | "
            "setup_running=%s | repair_running=%s",
            self._installation.initial_running,
            self._installation.setup_running,
            self._repair.running,
        )

    def _has_active_work(self) -> bool:
        """Return whether the installer still owns any background worker."""

        return (
            self._installation.initial_running
            or self._installation.setup_running
            or self._repair.running
        )


__all__ = ["InstallationCloseCoordinator"]
