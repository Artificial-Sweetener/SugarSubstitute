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

from PySide6.QtCore import QObject, QThread, Signal, Slot

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
    RepairPreparation,
    RepairPreparationService,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)


class RepairPreparationWorker(QObject):
    """Stage immutable release artifacts and publish a detached handoff request."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        layout: InstallLayout,
        release_source: ReleaseManifestSource,
        scope: RepairScope,
    ) -> None:
        """Store exact source and target boundaries for one preparation."""

        super().__init__()
        self._layout = layout
        self._release_source = release_source
        self._scope = scope

    @Slot()
    def run(self) -> None:
        """Prepare repair artifacts while leaving active installation files untouched."""

        try:
            preparation = RepairPreparationService().prepare_bound_application_repair(
                layout=self._layout,
                release_source=self._release_source,
                scope=self._scope,
            )
        except Exception as error:
            self.failed.emit(launcher_failure_detail(error))
            self.finished.emit()
            return
        self.succeeded.emit(preparation)
        self.finished.emit()


class QtRepairPreparationExecutor(QObject):
    """Own one repair preparation thread and deterministic cleanup."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize an idle preparation slot."""

        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: RepairPreparationWorker | None = None

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

        if self._thread is not None:
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
        worker.failed.connect(self.failed.emit)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._finish)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    @Slot()
    def _finish(self) -> None:
        """Release worker ownership before publishing completion."""

        self._thread = None
        self._worker = None
        self.finished.emit()


def require_repair_preparation(result: object) -> RepairPreparation:
    """Narrow an emitted Qt payload to the authoritative preparation value."""

    if not isinstance(result, RepairPreparation):
        raise TypeError("Repair preparation worker returned an invalid result.")
    return result


__all__ = ["QtRepairPreparationExecutor", "require_repair_preparation"]
