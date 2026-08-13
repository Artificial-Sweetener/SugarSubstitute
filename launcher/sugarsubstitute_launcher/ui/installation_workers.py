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

"""Adapt blocking installation workflow stages to Qt worker signals."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, Signal, Slot

from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
)
from launcher.sugarsubstitute_launcher.application.installation.release_source_policy import (
    create_initial_installation_request,
)
from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)


InstallationWorkflowFactory = Callable[
    [Callable[[str], None]],
    InstallationWorkflow,
]


class SetupWorker(QObject):
    """Provision the runtime and hand off setup away from the UI thread."""

    log = Signal(str)
    failed = Signal(str, str)
    succeeded = Signal()
    finished = Signal()

    def __init__(
        self,
        *,
        application: InstalledApplication,
        setup_command: Sequence[str],
        workflow_factory: InstallationWorkflowFactory,
    ) -> None:
        """Store setup work that must not block the Qt event loop."""

        super().__init__()
        self._application = application
        self._setup_command = list(setup_command)
        self._workflow_factory = workflow_factory

    @Slot()
    def run(self) -> None:
        """Provision the runtime, launch setup, and report progress through signals."""

        workflow = self._workflow_factory(self.log.emit)
        try:
            completed = workflow.provision_runtime(self._application)
        except Exception as error:
            self.failed.emit("runtime", launcher_failure_detail(error))
            self.finished.emit()
            return

        self.log.emit(launcher_text("Runtime ready: %1", completed.runtime_python))
        self.log.emit(launcher_text("Starting SugarSubstitute setup."))
        try:
            workflow.start_setup(self._setup_command)
        except Exception as error:
            self.failed.emit("setup", launcher_failure_detail(error))
            self.finished.emit()
            return

        self.log.emit(launcher_text("Started SugarSubstitute setup."))
        self.log.emit(launcher_text("Waiting for the setup window to open."))
        self.succeeded.emit()
        self.finished.emit()


class InitialInstallWorker(QObject):
    """Install launcher and app payload without blocking the setup window."""

    log = Signal(str)
    failed = Signal(str)
    succeeded = Signal(object)
    finished = Signal()

    def __init__(
        self,
        *,
        layout: InstallLayout,
        frozen_setup: bool,
        handoff_geometry: str | None,
        workflow_factory: InstallationWorkflowFactory,
    ) -> None:
        """Store initial install work that runs away from the Qt event loop."""

        super().__init__()
        self._layout = layout
        self._frozen_setup = frozen_setup
        self._handoff_geometry = handoff_geometry
        self._workflow_factory = workflow_factory

    @Slot()
    def run(self) -> None:
        """Install permanent launcher files and the app payload."""

        try:
            workflow = self._workflow_factory(self.log.emit)
            request = create_initial_installation_request(
                layout=self._layout,
                frozen_setup=self._frozen_setup,
                handoff_geometry=self._handoff_geometry,
            )
            application = workflow.install_application(request)
            if application.launcher_installed:
                self.log.emit(
                    launcher_text(
                        "Installed launcher: %1",
                        application.layout.executable_path,
                    )
                )
            else:
                self.log.emit(
                    launcher_text(
                        "Source-run launcher detected; skipped executable self-copy."
                    )
                )

            self.log.emit(
                launcher_text("Created install root: %1", application.layout.root)
            )
            self.log.emit(
                launcher_text(
                    "Wrote launcher config: %1",
                    application.layout.config_path,
                )
            )
        except Exception as error:
            self.failed.emit(launcher_failure_detail(error))
            self.finished.emit()
            return

        self.succeeded.emit(application)
        self.finished.emit()
