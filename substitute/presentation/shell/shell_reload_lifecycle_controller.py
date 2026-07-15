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

"""Coordinate shell detachment before GUI reload disposal."""

from __future__ import annotations

from typing import Protocol

from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)


class _DisposableController(Protocol):
    """Describe one shell controller with explicit observer disposal."""

    def dispose(self) -> None:
        """Detach the controller from its external observers."""


class _ShellReloadView(Protocol):
    """Describe shell state required for synchronous reload detachment."""

    _detached_for_gui_reload: bool
    _generation_job_queue_observer: object
    generation_job_queue_service: object
    node_definition_refresh_controller: _DisposableController
    shell_resource_lifecycle: ShellResourceLifecycle


class ShellReloadLifecycleController:
    """Own cleanup required before a MainWindow instance is replaced."""

    def __init__(self, shell: _ShellReloadView) -> None:
        """Store the shell whose long-lived observers should be detached."""

        self._shell = shell
        self._is_detached = False

    def detach_for_gui_reload(self) -> None:
        """Detach UI observers and synchronously release shell resources."""

        if self._is_detached:
            return
        self._is_detached = True

        self._shell._detached_for_gui_reload = True
        self._shell.node_definition_refresh_controller.dispose()
        remove_observer = getattr(
            self._shell.generation_job_queue_service,
            "remove_observer",
            None,
        )
        if callable(remove_observer):
            remove_observer(self._shell._generation_job_queue_observer)
        for disposable in (
            getattr(self._shell, "_generation_queue_dropdown", None),
            getattr(self._shell, "generationQueuePanel", None),
        ):
            dispose = getattr(disposable, "dispose", None)
            if callable(dispose):
                dispose()
        self._shell.shell_resource_lifecycle.shutdown_or_raise()


__all__ = ["ShellReloadLifecycleController"]
