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

"""Own generation queue flyout, menu, and side-panel presentation."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.generation.queue_dropdown import GenerationQueueDropdown
from substitute.presentation.generation.queue_panel import GenerationQueuePanel
from substitute.presentation.shell.generation_result_workspace_opener import (
    open_generation_job_as_workflow_for_view,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer


class GenerationQueueController:
    """Coordinate shell-owned generation queue surfaces."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose generation queue surfaces are controlled."""

        self._shell = shell
        self._dropdown: GenerationQueueDropdown | None = None
        self._panel: GenerationQueuePanel | None = None
        self._panel_visible = False

    @property
    def panel_visible(self) -> bool:
        """Return the target visibility owned by the queue presentation."""

        return self._panel_visible

    def install_surfaces(self) -> None:
        """Create queue flyout and side-panel widgets for the shell."""

        self._dropdown = GenerationQueueDropdown(
            self._shell.generation_job_queue_service,
            parent=self._shell,
            open_snapshot_requested=self.open_generation_snapshot,
        )
        self._panel = GenerationQueuePanel(
            self._shell.generation_job_queue_service,
            open_snapshot_requested=self.open_generation_snapshot,
            parent=self._shell.sidePanelHost,
        )
        self._panel.hideRequested.connect(lambda: self.set_panel_visible(False))
        self._shell.sidePanelHost.set_queue_panel(self._panel)
        self._shell._generation_queue_dropdown = self._dropdown
        self._shell.generationQueuePanel = self._panel

    def open_generation_snapshot(self, job_id: str) -> None:
        """Open a queue job through the generation-result workspace owner."""

        open_generation_job_as_workflow_for_view(
            generation_view=self._shell,
            file_actions=self._shell.workspace_file_actions,
            job_id=job_id,
        )

    def show_for(self, target: QWidget) -> None:
        """Toggle the queue dropdown anchored to a titlebar segment."""

        self._queue_dropdown().toggle_for(target)

    def show_context_menu_for(self, target: QWidget) -> None:
        """Show queue display options anchored to the titlebar segment."""

        panel_visible = self.panel_visible
        action_label = (
            app_text("Hide Full Queue Panel")
            if panel_visible
            else app_text("Show Full Queue Panel")
        )
        action_icon = (
            AppIcon.PANEL_RIGHT_20_FILLED
            if panel_visible
            else AppIcon.PANEL_RIGHT_20_REGULAR
        )
        menu = QFluentMenuRenderer(parent=target).render(
            MenuModel(
                entries=(
                    MenuItem(
                        "generation_queue.toggle_panel",
                        action_label,
                        callback=lambda: self.set_panel_visible(not panel_visible),
                        icon=action_icon,
                    ),
                ),
            )
        )
        menu.exec(
            target.mapToGlobal(QPoint(0, target.height())),
            aniType=MenuAnimationType.DROP_DOWN,
        )

    def set_panel_visible(self, visible: bool) -> None:
        """Set queue side-panel visibility for a user request."""

        self.apply_panel_visibility(
            visible,
            request_autosave=True,
        )

    def apply_panel_visibility(
        self,
        visible: bool,
        *,
        request_autosave: bool,
        animated: bool = True,
    ) -> None:
        """Set queue panel target visibility and refresh derived shell controls."""

        self._panel_visible = visible
        self._shell._generation_queue_panel_visible = visible
        transition = getattr(self._shell, "_generation_queue_panel_transition", None)
        if animated and transition is not None:
            transition.transition_to(visible)
        else:
            self._shell.sidePanelHost.set_queue_panel_visible(visible)
        self._shell.generation_action_controller.apply_generation_action_availability()
        if request_autosave:
            self._shell.request_session_autosave()

    def _queue_dropdown(self) -> GenerationQueueDropdown:
        """Return the installed queue dropdown."""

        if self._dropdown is not None:
            return self._dropdown
        dropdown = getattr(self._shell, "_generation_queue_dropdown", None)
        return cast(GenerationQueueDropdown, dropdown)


def generation_queue_controller_for(shell: Any) -> GenerationQueueController:
    """Return the composed generation queue controller for a shell."""

    controller = getattr(shell, "generation_queue_controller", None)
    if isinstance(controller, GenerationQueueController):
        return controller
    controller = GenerationQueueController(shell)
    setattr(shell, "generation_queue_controller", controller)
    return controller


__all__ = ["GenerationQueueController", "generation_queue_controller_for"]
