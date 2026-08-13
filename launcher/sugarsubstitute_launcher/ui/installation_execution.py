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

"""Own Qt thread lifecycles for blocking installation workflow adapters."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, QThread, Signal, Slot

from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.installation_workers import (
    InitialInstallWorker,
    InstallationWorkflowFactory,
    SetupWorker,
)


class QtInstallationExecutor(QObject):
    """Run installation workers and publish results after deterministic cleanup."""

    log = Signal(str)
    initial_failed = Signal(str)
    initial_succeeded = Signal(object)
    initial_finished = Signal()
    setup_failed = Signal(str, str)
    setup_succeeded = Signal()
    setup_finished = Signal()

    def __init__(
        self,
        *,
        workflow_factory: InstallationWorkflowFactory,
        parent: QObject | None = None,
    ) -> None:
        """Store workflow composition and initialize idle execution slots."""

        super().__init__(parent)
        self._workflow_factory = workflow_factory
        self._initial_thread: QThread | None = None
        self._initial_worker: InitialInstallWorker | None = None
        self._setup_thread: QThread | None = None
        self._setup_worker: SetupWorker | None = None

    @property
    def initial_running(self) -> bool:
        """Return whether launcher and payload installation is still running."""

        return self._initial_thread is not None

    @property
    def setup_running(self) -> bool:
        """Return whether runtime provisioning and setup handoff is still running."""

        return self._setup_thread is not None

    def start_initial(
        self,
        *,
        layout: InstallLayout,
        frozen_setup: bool,
        handoff_geometry: str | None,
    ) -> bool:
        """Start launcher and app installation unless that stage is already active."""

        if self._initial_thread is not None:
            return False
        thread = QThread(self)
        worker = InitialInstallWorker(
            layout=layout,
            frozen_setup=frozen_setup,
            handoff_geometry=handoff_geometry,
            workflow_factory=self._workflow_factory,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self.log.emit)
        worker.failed.connect(self.initial_failed.emit)
        worker.succeeded.connect(self.initial_succeeded.emit)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._finish_initial)
        self._initial_thread = thread
        self._initial_worker = worker
        thread.start()
        return True

    def start_setup(
        self,
        *,
        application: InstalledApplication,
        setup_command: Sequence[str],
    ) -> bool:
        """Start runtime provisioning and setup handoff unless already active."""

        if self._setup_thread is not None:
            return False
        thread = QThread(self)
        worker = SetupWorker(
            application=application,
            setup_command=setup_command,
            workflow_factory=self._workflow_factory,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self.log.emit)
        worker.failed.connect(self.setup_failed.emit)
        worker.succeeded.connect(self.setup_succeeded.emit)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._finish_setup)
        self._setup_thread = thread
        self._setup_worker = worker
        thread.start()
        return True

    @Slot()
    def _finish_initial(self) -> None:
        """Release initial-install objects before publishing stage completion."""

        self._initial_thread = None
        self._initial_worker = None
        self.initial_finished.emit()

    @Slot()
    def _finish_setup(self) -> None:
        """Release setup objects before publishing stage completion."""

        self._setup_thread = None
        self._setup_worker = None
        self.setup_finished.emit()
