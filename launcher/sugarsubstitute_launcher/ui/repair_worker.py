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

from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.repair_process_supervisor import (
    RepairProcessCancelled,
    RepairProcessSupervisor,
)
from launcher.sugarsubstitute_launcher.repair_execution_command import (
    build_repair_execution_command,
)
from launcher.sugarsubstitute_launcher.repair_execution_progress import (
    repair_progress_from_message,
)
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)
from sugarsubstitute_shared.session_recovery import SessionRecoveryResult


_LOGGER = logging.getLogger(__name__)


class RepairWorker(QObject):
    """Run recovery and repair away from the window's event loop."""

    progress = Signal(object)
    output = Signal(str)
    session_recovery = Signal(object)
    succeeded = Signal()
    failed = Signal(str)
    cancelled = Signal()
    fatal_failure = Signal()
    finished = Signal()

    def __init__(
        self,
        request: PreparedRepairRequest,
        *,
        supervisor: RepairProcessSupervisor | None = None,
    ) -> None:
        """Retain one process owner until every terminal resource has been released."""
        super().__init__()
        self._request = request
        self._supervisor = supervisor or RepairProcessSupervisor(
            command_builder=lambda: build_repair_execution_command(request),
            startup_log_path=request.install_root
            / ".repair"
            / "diagnostics"
            / "repair-execution.log",
        )

    def request_cancel(self) -> None:
        """Accept UI-thread cancellation without performing native work on that thread."""
        self._supervisor.request_cancel()

    @Slot()
    def run(self) -> None:
        """Adapt the Qt-free execution owner to one terminal signal sequence."""
        try:
            terminal = self._supervisor.run(
                progress_observer=self._progress,
                output_callback=self.output.emit,
            )
            session_recovery = SessionRecoveryResult.from_json(
                terminal.get("session_recovery")
            )
        except RepairProcessCancelled:
            _LOGGER.info("Repair execution cancelled after owned process cleanup")
            self.cancelled.emit()
        except Exception as error:
            _LOGGER.exception(
                "Repair attempt failed",
                extra={
                    "repair_version": self._request.version,
                    "repair_scope": self._request.scope.value,
                },
            )
            if self._supervisor.safe_to_close:
                self.failed.emit(launcher_failure_detail(error))
            else:
                _LOGGER.critical(
                    "Repair cleanup could not be verified; retiring supervised host"
                )
                self.fatal_failure.emit()
        else:
            self.session_recovery.emit(session_recovery)
            self.succeeded.emit()
        finally:
            self.finished.emit()

    def _progress(self, message: dict[str, object]) -> None:
        """Validate execution-domain counts before publishing to Qt presentation."""
        self.progress.emit(repair_progress_from_message(message))
