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

"""Adapt one recoverable repair execution to queued Qt progress signals."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

from launcher.sugarsubstitute_launcher.application.repair.composition import (
    build_repair_execution_service,
)
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.platforms import launcher_target_for_key
from launcher.sugarsubstitute_launcher.repair_recovery import recover_interrupted_repair
from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)


_LOGGER = logging.getLogger(__name__)


class RepairWorker(QObject):
    """Run recovery and repair away from the window's event loop."""

    progress = Signal(object)
    output = Signal(str)
    succeeded = Signal()
    failed = Signal(str)
    finished = Signal()

    def __init__(self, request: PreparedRepairRequest) -> None:
        """Retain immutable retry inputs for one worker attempt."""
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        """Recover interrupted mutations before executing a fresh candidate."""
        try:
            recover_interrupted_repair(self._request.install_root)
            service = build_repair_execution_service(
                target=launcher_target_for_key(self._request.target_key),
                progress_observer=self.progress.emit,
                output_callback=self.output.emit,
            )
            run_prepared_repair(
                self._request.install_root / ".repair" / "prepared.json",
                executor=service.execute_application,
            )
        except Exception as error:
            _LOGGER.exception(
                "Repair attempt failed",
                extra={
                    "repair_version": self._request.version,
                    "repair_scope": self._request.scope.value,
                },
            )
            self.failed.emit(launcher_failure_detail(error))
        else:
            self.succeeded.emit()
        finally:
            self.finished.emit()
