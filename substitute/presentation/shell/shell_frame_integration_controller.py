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

"""Coordinate shell-frame controls attached outside the MainWindow body."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.application.comfy_startup_diagnostics import (
    StartupDiagnosticsTitlebarState,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from substitute.presentation.shell.startup_diagnostics_titlebar_controller import (
    StartupDiagnosticsTitlebarController,
)
from substitute.presentation.shell.taskbar_progress import (
    NoOpTaskbarProgressPresenter,
    TaskbarProgressPresenter,
)
from substitute.presentation.shell.titlebar_buttons import (
    StartupDiagnosticsTitleBarButton,
)


class ShellFrameIntegrationController:
    """Own frame-provided titlebar, taskbar, and app-orb attachments."""

    def __init__(self, shell: Any) -> None:
        """Store the shell and install default external-frame state."""

        self._shell = shell
        self._startup_diagnostics_titlebar_controller: (
            StartupDiagnosticsTitlebarController | None
        ) = None
        self._pending_startup_diagnostics_state: (
            StartupDiagnosticsTitlebarState | None
        ) = None
        self._shell._taskbar_progress_presenter = NoOpTaskbarProgressPresenter()

    def set_taskbar_progress_presenter(
        self,
        presenter: TaskbarProgressPresenter,
    ) -> None:
        """Install the taskbar progress presenter owned by the shell frame."""

        self._shell._taskbar_progress_presenter = presenter

    def attach_startup_diagnostics_titlebar(
        self,
        button: StartupDiagnosticsTitleBarButton,
        ignore_repository: StartupDiagnosticsIgnoreRepository,
    ) -> None:
        """Attach the startup diagnostics titlebar indicator to the shell."""

        self._startup_diagnostics_titlebar_controller = (
            StartupDiagnosticsTitlebarController(
                button=button,
                parent=cast(QWidget, self._shell),
                ignore_repository=ignore_repository,
            )
        )
        if self._pending_startup_diagnostics_state is not None:
            self.set_startup_diagnostics_state(self._pending_startup_diagnostics_state)

    def set_startup_diagnostics_state(
        self,
        state: StartupDiagnosticsTitlebarState | None,
    ) -> None:
        """Expose startup diagnostics through the shell titlebar indicator."""

        self._pending_startup_diagnostics_state = state
        if self._startup_diagnostics_titlebar_controller is None:
            return
        self._startup_diagnostics_titlebar_controller.set_state(state)

    def set_generation_titlebar_control_registry(
        self,
        registry: GenerationTitleBarControlRegistry,
    ) -> None:
        """Attach the shared generation titlebar control registry to the shell."""

        self._shell.generation_titlebar_control_registry = registry
        generation_action_cluster = getattr(
            self._shell, "generationActionCluster", None
        )
        mode_callback = getattr(
            self._shell,
            "_generation_action_cluster_mode_callback",
            None,
        )
        if generation_action_cluster is not None and mode_callback is not None:
            try:
                generation_action_cluster.generateModeSelected.disconnect(mode_callback)
            except RuntimeError:
                pass
            self._shell._generation_action_cluster_mode_callback = None
        if generation_action_cluster is not None:
            registry.register(generation_action_cluster)
        self._shell.output_floating_chrome_factory.set_titlebar_control_registry(
            registry
        )

    def attach_app_orb_menu(self, app_orb_menu: object) -> None:
        """Connect the frame-owned app orb menu to controller entry points."""

        self._shell.main_window_signal_binder.attach_app_orb_menu(app_orb_menu)

    def set_reopen_closed_workflow_enabled(self, enabled: bool) -> None:
        """Toggle the tab-bar reopen command from closed workflow buffer state."""

        set_enabled = getattr(
            self._shell.workflow_tabbar,
            "set_reopen_closed_workflow_enabled",
            None,
        )
        if callable(set_enabled):
            set_enabled(enabled)


__all__ = ["ShellFrameIntegrationController"]
