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

"""Run exact-version repair preparation outside the Qt presentation thread."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparation,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.repair_preparation_worker import (
    RepairPreparationWorker,
)


class QtRepairPreparationExecutor(QObject):
    """Own one repair preparation thread and deterministic cleanup."""

    succeeded = Signal(object)
    progress = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize an idle preparation slot."""

        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: RepairPreparationWorker | None = None
        self._retire_host = False

    @property
    def running(self) -> bool:
        """Return whether immutable artifact preparation is active."""

        return self._thread is not None

    def start(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        scope: RepairScope = RepairScope.APPLICATION,
    ) -> bool:
        """Start one preparation unless a previous operation still owns the slot."""

        if self._thread is not None or self._retire_host:
            return False
        thread = QThread(self)
        worker = RepairPreparationWorker(
            layout=layout,
            release_source=release_source,
            scope=scope,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self.succeeded.emit)
        worker.progress.connect(self.progress.emit)
        worker.failed.connect(self.failed.emit)
        worker.fatal_failure.connect(self._fatal_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._finish)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def request_cancel(self) -> None:
        """Forward Close to the active operation's thread-safe cancellation owner."""
        if self._worker is not None:
            self._worker.request_cancel()

    @Slot()
    def _fatal_failure(self) -> None:
        """Retire this host after joining its worker when native cleanup is unverified."""
        self._retire_host = True

    @Slot()
    def _finish(self) -> None:
        """Join native worker destruction before releasing preparation wrappers."""

        if self._thread is not None:
            self._thread.wait()
        self._thread = None
        self._worker = None
        if self._retire_host:
            QCoreApplication.exit(1)
            return
        self.finished.emit()


def require_repair_preparation(result: object) -> RepairPreparation:
    """Narrow an emitted Qt payload to the authoritative preparation value."""

    if not isinstance(result, RepairPreparation):
        raise TypeError("Repair preparation worker returned an invalid result.")
    return result


__all__ = ["QtRepairPreparationExecutor", "require_repair_preparation"]
