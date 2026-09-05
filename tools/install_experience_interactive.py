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

"""Join synthetic launcher handoff to interactive production ComfyUI setup."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from PySide6.QtWidgets import QApplication

from launcher.sugarsubstitute_launcher.application.installation.models import (
    ArtifactInstaller,
    LayoutPreparer,
    ReleaseManifestSource,
    RuntimeProvisioner,
)
from launcher.sugarsubstitute_launcher.application.installation.workflow import (
    InstallationWorkflow,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tools.install_experience_onboarding import (
    OnboardingCheckSession,
    open_interactive_onboarding,
)


def run_interactive_full_experience(
    *,
    application: QApplication,
    artifact_root: Path,
    release_source: ReleaseManifestSource,
) -> int:
    """Hand the synthetic bootstrap launcher into production ComfyUI setup."""

    install_root = artifact_root / "interactive" / "synthetic-install"
    sessions: list[OnboardingCheckSession] = []
    window = LauncherMainWindow(
        initial_layout=InstallLayout.from_root(install_root),
        continue_install=False,
        repair=False,
        update_check_enabled=False,
        initial_release_source=release_source,
        workflow_factory=_synthetic_workflow_factory(),
    )

    def show_comfy_setup() -> None:
        """Open the next production install stage in the same Qt process."""

        session = open_interactive_onboarding(
            install_root=install_root,
            install_root_locked=True,
        )
        sessions.append(session)

    window.handoff_completed.connect(show_comfy_setup)
    window.show()
    try:
        return int(application.exec())
    finally:
        for session in sessions:
            session.close()
        window.close()
        window.deleteLater()


def _synthetic_workflow_factory() -> Callable[
    [Callable[[str], None]], InstallationWorkflow
]:
    """Build an in-memory launcher workflow for the explicit full walkthrough."""

    class SyntheticLayoutPreparer:
        """Return the requested layout without creating it."""

        def prepare(self, install_root: Path) -> object:
            """Return a synthetic preparation result."""

            return SimpleNamespace(layout=InstallLayout.from_root(install_root))

    class SyntheticArtifactInstaller:
        """Return payload metadata without downloading or writing artifacts."""

        def install_downloaded_launcher(
            self,
            *,
            install_root: Path,
            release_source: object,
            handoff_geometry: str | None,
            launch_installed: bool,
        ) -> object:
            """Return a synthetic installed-launcher result."""

            _ = (release_source, handoff_geometry, launch_installed)
            return SimpleNamespace(layout=InstallLayout.from_root(install_root))

        def continue_install(
            self,
            *,
            layout: InstallLayout,
            release_source: object,
        ) -> object:
            """Return a synthetic application payload result."""

            _ = release_source
            return SimpleNamespace(
                layout=layout,
                app_version="qualification",
                app_command=("synthetic-python", "main.py"),
            )

    class SyntheticRuntimeProvisioner:
        """Return a runtime path without creating an environment."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Return the layout's unmaterialized Python path."""

            return SimpleNamespace(python_executable=layout.runtime_python)

    def create_workflow(_log: Callable[[str], None]) -> InstallationWorkflow:
        """Compose the real workflow over inert boundary implementations."""

        return InstallationWorkflow(
            layout_preparer=cast(LayoutPreparer, SyntheticLayoutPreparer()),
            artifact_installer=cast(ArtifactInstaller, SyntheticArtifactInstaller()),
            runtime_provisioner=cast(
                RuntimeProvisioner,
                SyntheticRuntimeProvisioner(),
            ),
            process_starter=lambda _command: None,
        )

    return create_workflow


__all__ = ["run_interactive_full_experience"]
