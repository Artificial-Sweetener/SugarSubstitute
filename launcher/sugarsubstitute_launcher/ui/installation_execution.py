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

"""Run launcher installation operations away from the Qt presentation thread."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal, Slot

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.initial_release_source import (
    resolve_initial_install_release_source,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.failure_detail import (
    launcher_failure_detail,
)


class LauncherRuntimeInstaller(Protocol):
    """Provision the runtime required to start the installed source app."""

    def provision(self, *, layout: InstallLayout) -> object:
        """Ensure the runtime exists for the supplied install layout."""


RuntimeInstallerFactory = Callable[[Callable[[str], None]], LauncherRuntimeInstaller]


class SetupWorker(QObject):
    """Run runtime provisioning and app handoff away from the UI thread."""

    log = Signal(str)
    failed = Signal(str, str)
    succeeded = Signal()
    finished = Signal()

    def __init__(
        self,
        *,
        layout: InstallLayout,
        setup_command: Sequence[str],
        runtime_installer_factory: RuntimeInstallerFactory,
        process_starter: Callable[[Sequence[str]], None],
    ) -> None:
        """Store setup work that must not block the Qt event loop."""

        super().__init__()
        self._layout = layout
        self._setup_command = list(setup_command)
        self._runtime_installer_factory = runtime_installer_factory
        self._process_starter = process_starter

    @Slot()
    def run(self) -> None:
        """Provision the runtime, launch setup, and publish terminal signals."""

        try:
            runtime_installer = self._runtime_installer_factory(self.log.emit)
            runtime_installer.provision(layout=self._layout)
        except Exception as error:
            self.failed.emit("runtime", launcher_failure_detail(error))
            self.finished.emit()
            return

        self.log.emit(launcher_text("Runtime ready: %1", self._layout.runtime_python))
        self.log.emit(launcher_text("Starting SugarSubstitute setup."))
        try:
            self._process_starter(self._setup_command)
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
    succeeded = Signal(object, object, str)
    finished = Signal()

    def __init__(
        self,
        *,
        install_root: Path,
        frozen_setup: bool,
        handoff_geometry: str | None,
        layout_installer: LayoutInstaller,
        first_run_installer: FirstRunInstaller,
    ) -> None:
        """Store initial install work that runs away from the Qt event loop."""

        super().__init__()
        self._install_root = install_root
        self._frozen_setup = frozen_setup
        self._handoff_geometry = handoff_geometry
        self._layout_installer = layout_installer
        self._first_run_installer = first_run_installer

    @Slot()
    def run(self) -> None:
        """Install permanent launcher files and the bound app payload."""

        try:
            release_source = resolve_initial_install_release_source(
                frozen_setup=self._frozen_setup
            )
            if self._frozen_setup:
                downloaded_result = (
                    self._first_run_installer.install_downloaded_launcher(
                        install_root=self._install_root,
                        release_source=release_source,
                        handoff_geometry=self._handoff_geometry,
                        launch_installed=False,
                    )
                )
                layout = downloaded_result.layout
                self.log.emit(
                    launcher_text("Installed launcher: %1", layout.executable_path)
                )
            else:
                prepared_result = self._layout_installer.prepare(self._install_root)
                layout = prepared_result.layout
                self.log.emit(
                    launcher_text(
                        "Source-run launcher detected; skipped executable self-copy."
                    )
                )

            self.log.emit(launcher_text("Created install root: %1", layout.root))
            self.log.emit(
                launcher_text("Wrote launcher config: %1", layout.config_path)
            )
            continued_result = self._first_run_installer.continue_install(
                layout=layout,
                release_source=release_source,
            )
        except Exception as error:
            self.failed.emit(launcher_failure_detail(error))
            self.finished.emit()
            return

        self.succeeded.emit(
            layout,
            continued_result.app_command,
            continued_result.app_version,
        )
        self.finished.emit()


__all__ = [
    "InitialInstallWorker",
    "LauncherRuntimeInstaller",
    "RuntimeInstallerFactory",
    "SetupWorker",
]
