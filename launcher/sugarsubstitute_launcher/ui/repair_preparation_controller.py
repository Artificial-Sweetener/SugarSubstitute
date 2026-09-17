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

"""Coordinate immutable repair preparation and the handoff into supervised replacement."""

from __future__ import annotations

import logging
from collections.abc import Callable
from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QWidget
from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.repair_handoff import (
    launch_prepared_repair_helper,
)
from launcher.sugarsubstitute_launcher.ui.experience_models import RepairChoice
from launcher.sugarsubstitute_launcher.ui.experience_pages import RepairScopePage
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)
from launcher.sugarsubstitute_launcher.ui.installer_failure_presenter import (
    InstallerFailurePresenter,
)
from launcher.sugarsubstitute_launcher.ui.repair_preparation_execution import (
    QtRepairPreparationExecutor,
    require_repair_preparation,
)

_LOGGER = logging.getLogger(__name__)


class RepairPreparationController(QObject):
    """Own preparation actions while deriving worker lifetime from its executor."""

    def __init__(
        self,
        *,
        window: QWidget,
        page: RepairScopePage,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        execution: QtRepairPreparationExecutor,
        close_requested: Callable[[], bool],
        handoff_completed: Callable[[], None],
        failure_presenter: InstallerFailurePresenter,
    ) -> None:
        """Bind one preparation workflow without taking over window-close authority."""
        super().__init__(window)
        self._window = window
        self._page = page
        self._layout = layout
        self._release_source = release_source
        self._execution = execution
        self._close_requested = close_requested
        self._handoff_completed = handoff_completed
        self._failure_presenter = failure_presenter
        execution.succeeded.connect(self._prepared)
        execution.failed.connect(self._failed)
        execution.progress.connect(self._progress)
        page.continue_requested.connect(self.start)

    @property
    def running(self) -> bool:
        """Expose the executor's current lifetime without retaining another busy flag."""
        return self._execution.running

    @Slot(object)
    def _progress(self, value: object) -> None:
        """Project the worker's authoritative progress on the presentation thread."""
        if not isinstance(value, PreparationProgress):
            raise TypeError("Repair preparation emitted invalid progress.")
        self._page.preparation_progress.set_progress(value)

    def start(self) -> None:
        """Prepare the explicitly selected repair before detached replacement."""

        if self._execution.running:
            return
        scope = (
            RepairScope.FULL_MANAGED_COMFY
            if self._page.choice is RepairChoice.FULL_MANAGED_COMFY
            else RepairScope.APPLICATION
        )
        self._page.set_status(
            launcher_text(
                "Downloading and verifying this installer's exact release. "
                "Your active installation has not been changed yet."
            ),
            working=True,
        )
        self._execution.start(
            layout=self._layout,
            release_source=self._release_source,
            scope=scope,
        )

    @Slot(object)
    def _prepared(self, result: object) -> None:
        """Launch the independent helper only after every artifact is verified."""

        if self._close_requested():
            return
        try:
            preparation = require_repair_preparation(result)
            request = preparation.request.with_process_behavior(
                wait_pid=None,
                wait_process_created_at=None,
                relaunch=True,
            )
            request.save(preparation.request_path)
            launch_prepared_repair_helper(request_path=preparation.request_path)
        except Exception as error:
            _LOGGER.exception("Could not hand off prepared repair.")
            self._failed(launcher_failure_detail(error))
            return
        self._page.set_status(
            launcher_text("Repair is ready. Closing this window to replace app files."),
            working=True,
        )
        self._handoff_completed()
        QTimer.singleShot(0, self._window.close)

    @Slot(str)
    def _failed(self, details: str) -> None:
        """Restore the repair action after a staging or handoff failure."""

        self._page.set_status(
            launcher_text(
                "Repair could not be prepared. Nothing in the active installation was changed. Details: %1",
                details,
            ),
            working=False,
        )
        self._failure_presenter.show_failure(
            stage=launcher_text("Prepare repair"),
            details=details,
        )
