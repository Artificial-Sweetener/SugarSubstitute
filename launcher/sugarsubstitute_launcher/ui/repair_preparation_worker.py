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

"""Adapt supervised preparation to queued Qt observations and terminal outcomes."""

import logging

from PySide6.QtCore import QObject, Signal, Slot

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.repair_preparation_operation import (
    RepairPreparationOperation,
)
from launcher.sugarsubstitute_launcher.repair_process_supervisor import (
    RepairProcessCancelled,
)
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)

_LOGGER = logging.getLogger(__name__)


class RepairPreparationWorker(QObject):
    """Retain one operation until native cleanup determines the terminal Qt outcome."""

    succeeded = Signal(object)
    progress = Signal(object)
    failed = Signal(str)
    fatal_failure = Signal()
    finished = Signal()

    def __init__(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        scope: RepairScope,
    ) -> None:
        """Create the sole cancellation owner before the worker thread is admitted."""
        super().__init__()
        self._operation = RepairPreparationOperation(
            layout=layout, release_source=release_source, scope=scope
        )

    def request_cancel(self) -> None:
        """Forward Close without waiting for a queued slot on a busy worker thread."""
        self._operation.request_cancel()

    @Slot()
    def run(self) -> None:
        """Publish success or failure only after the operation has released its family."""
        try:
            preparation = self._operation.run(progress_observer=self.progress.emit)
        except RepairProcessCancelled:
            _LOGGER.info("Repair preparation cancelled after native cleanup")
        except Exception as error:
            _LOGGER.exception("Repair preparation failed")
            if self._operation.safe_to_close:
                self.failed.emit(launcher_failure_detail(error))
            else:
                _LOGGER.critical(
                    "Preparation cleanup could not be verified; retiring supervised host"
                )
                self.fatal_failure.emit()
        else:
            self.succeeded.emit(preparation)
        finally:
            self.finished.emit()
