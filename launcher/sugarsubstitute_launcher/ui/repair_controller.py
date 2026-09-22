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

"""Own repair worker lifetime and explicit recovery actions for one visible window."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QObject, QThread, Slot

from launcher.sugarsubstitute_launcher.application.repair.progress import RepairProgress
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.ui.repair_stage_text import repair_stage_text
from launcher.sugarsubstitute_launcher.ui.repair_window import RepairWindow
from launcher.sugarsubstitute_launcher.ui.repair_worker import RepairWorker
from sugarsubstitute_shared.qt_application_instance_control import (
    request_supervised_application_restart,
)


class RepairController(QObject):
    """Keep every attempt alive through safe completion before honoring close or retry."""

    def __init__(
        self,
        window: RepairWindow,
        request: PreparedRepairRequest,
        *,
        worker_factory: Callable[[PreparedRepairRequest], RepairWorker] = RepairWorker,
        open_application: Callable[[], bool] = request_supervised_application_restart,
    ) -> None:
        """Bind a single window to its worker factory and supervisor-owned open action."""
        super().__init__(window)
        self._window = window
        self._request = request
        self._worker_factory = worker_factory
        self._open_application = open_application
        self._thread: QThread | None = None
        self._worker: RepairWorker | None = None
        self._succeeded = False
        self._failure = ""
        self._close_pending = False
        self._retire_host = False
        self._details: deque[str] = deque(maxlen=500)
        window.close_requested.connect(self._defer_close)
        window.primary_requested.connect(self._primary_action)

    @Slot()
    def start(self) -> None:
        """Start one attempt only after the host surface has painted."""
        if self._thread is not None or self._retire_host:
            return
        self._succeeded = False
        self._failure = ""
        self._details.clear()
        self._window.progress_view.begin_attempt()
        self._window.set_running(True)
        thread = QThread(self)
        worker = self._worker_factory(self._request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._progress)
        worker.output.connect(self._output)
        worker.succeeded.connect(self._success)
        worker.failed.connect(self._failed)
        worker.fatal_failure.connect(self._fatal_failure)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _progress(self, value: object) -> None:
        """Render executor-owned completed stages on the UI thread."""
        if not isinstance(value, RepairProgress):
            raise TypeError("Repair worker emitted an invalid progress event.")
        if value.stage is not None:
            self._window.progress_view.set_stage(
                repair_stage_text(value.stage),
                completed=value.completed,
                total=value.total,
            )

    @Slot(str)
    def _output(self, line: str) -> None:
        """Bound visible diagnostics and pulse only when output actually arrives."""
        self._details.append(line.rstrip())
        self._window.progress_view.set_details("\n".join(self._details))
        self._window.progress_view.pulse_activity()

    @Slot()
    def _success(self) -> None:
        """Retain completion until the worker thread has fully released its resources."""
        self._succeeded = True

    @Slot(str)
    def _failed(self, details: str) -> None:
        """Keep failure details for the terminal view without racing worker cleanup."""
        self._failure = details

    @Slot()
    def _finished(self) -> None:
        """Join native teardown before releasing the worker's Python wrapper.

        Qt can deliver finished while deferred worker destruction is still running
        on the native thread. Retain both wrappers until that destruction completes.
        """
        thread = self._thread
        if thread is not None:
            thread.wait()
        self._thread = None
        self._worker = None
        self._window.set_running(False)
        if self._retire_host:
            self._window.close()
            QCoreApplication.exit(1)
            return
        if self._close_pending:
            self._window.close()
            return
        self._window.progress_view.show_result(
            succeeded=self._succeeded,
            details=self._failure or "\n".join(self._details),
        )
        if self._succeeded and self._request.relaunch:
            self._primary_action()

    @Slot()
    def _defer_close(self) -> None:
        """Cancel the owned execution and close only after native cleanup completes."""
        self._close_pending = True
        if self._worker is not None:
            self._worker.request_cancel()

    @Slot()
    def _fatal_failure(self) -> None:
        """Delegate failed native cleanup to the host's outer process-family owner."""
        self._retire_host = True

    @Slot()
    def _primary_action(self) -> None:
        """Retry safely or ask the live supervisor to open the repaired application."""
        if self._thread is not None:
            return
        if not self._succeeded:
            self.start()
        elif self._open_application():
            self._window.close()
