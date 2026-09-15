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

"""Exercise queued repair work and user actions through the production controller."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QCoreApplication, QEvent, QThread, Slot
from PySide6.QtWidgets import QApplication, QPushButton

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.ui.repair_controller import RepairController
from launcher.sugarsubstitute_launcher.ui.repair_window import RepairWindow
from launcher.sugarsubstitute_launcher.ui.repair_worker import RepairWorker
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _request(root: Path) -> PreparedRepairRequest:
    """Provide inert request metadata for the controlled worker boundary."""
    staging = root / ".repair/staging/1.2.3"
    return PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        staging / "app",
        staging / "launcher",
        "a" * 64,
        "b" * 64,
    )


def _dispose(window: RepairWindow) -> None:
    """Wait for worker cleanup before disposing the native window and its children."""
    wait_for_qt_condition(
        lambda: not any(thread.isRunning() for thread in window.findChildren(QThread))
    )
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_close_waits_for_active_worker_completion(
    tmp_path: Path,
    qt_application_owner: QApplication,
) -> None:
    """A close request keeps the window and worker alive until mutation returns."""
    started, release = Event(), Event()

    class HeldWorker(RepairWorker):
        """Hold an external execution boundary until the test permits completion."""

        @Slot()
        def run(self) -> None:
            """Signal active work without blocking the Qt event loop."""
            started.set()
            if release.wait(10):
                self.succeeded.emit()
            else:
                self.failed.emit("Controlled worker timed out")
            self.finished.emit()

    window = RepairWindow()
    controller = RepairController(window, _request(tmp_path), worker_factory=HeldWorker)
    window.show()
    qt_application_owner.processEvents()
    try:
        controller.start()
        wait_for_qt_condition(started.is_set)
        assert not window.close()
        assert window.isVisible()
        release.set()
        wait_for_qt_condition(lambda: not window.isVisible())
    finally:
        release.set()
        _dispose(window)


def test_retry_and_open_wait_for_worker_cleanup(
    tmp_path: Path,
    qt_application_owner: QApplication,
) -> None:
    """Retry starts a new worker and successful Open delegates to the supervisor."""
    attempts: list[RepairWorker] = []
    opened: list[bool] = []

    class CompletedWorker(RepairWorker):
        """Return controlled outcomes through the production worker signal contract."""

        @Slot()
        def run(self) -> None:
            """Fail the first attempt and finish the retry successfully."""
            if len(attempts) == 1:
                self.failed.emit("Synthetic recoverable failure")
            else:
                self.succeeded.emit()
            self.finished.emit()

    def create(request: PreparedRepairRequest) -> RepairWorker:
        """Retain each distinct attempt for observable factory-call verification."""
        worker = CompletedWorker(request)
        attempts.append(worker)
        return worker

    def open_application() -> bool:
        """Record the successful supervisor action without launching an application."""
        opened.append(True)
        return True

    window = RepairWindow()
    controller = RepairController(
        window,
        _request(tmp_path),
        worker_factory=create,
        open_application=open_application,
    )
    window.show()
    qt_application_owner.processEvents()
    primary = window.findChild(QPushButton, "RepairPrimaryAction")
    assert primary is not None
    try:
        controller.start()
        wait_for_qt_condition(primary.isVisible)
        assert primary.text() == "Try again"
        primary.click()
        wait_for_qt_condition(primary.isVisible)
        assert len(attempts) == 2
        assert primary.text() == "Open SugarSubstitute"
        primary.click()
        assert opened == [True]
        assert not window.isVisible()
    finally:
        _dispose(window)
