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

"""Own Input canvas context commands and their current document targets."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from cutecanvas import MaskInfo
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer


class InputCanvasContextMenuController:
    """Resolve and render canvas commands from authoritative state on every opening."""

    def __init__(
        self,
        *,
        canvas: QWidget,
        active_mask_id_provider: Callable[[], UUID | None],
        mask_layers_provider: Callable[[], tuple[MaskInfo, ...]],
        coverage_edit_requested: Callable[[UUID], object],
        detached_provider: Callable[[], bool],
        dock_requested: Callable[[], object],
    ) -> None:
        """Bind narrow state providers without owning document or editor state."""

        self._canvas = canvas
        self._active_mask_id_provider = active_mask_id_provider
        self._mask_layers_provider = mask_layers_provider
        self._coverage_edit_requested = coverage_edit_requested
        self._detached_provider = detached_provider
        self._dock_requested = dock_requested

    def create_model(self) -> MenuModel:
        """Project the current editable mask and host attachment state into commands."""

        active_mask_id = self._active_editable_mask_id()
        return MenuModel(
            entries=(
                MenuItem(
                    action_id="input_canvas.edit_layer_coverage",
                    label=app_text("Edit layer coverage"),
                    callback=self._coverage_callback(active_mask_id),
                    enabled=active_mask_id is not None,
                ),
                MenuSeparator(),
                MenuItem(
                    action_id="input_canvas.dock_action",
                    label=app_text(
                        "Redock canvas"
                        if self._detached_provider()
                        else "Undock canvas"
                    ),
                    callback=self._dock_callback,
                ),
            )
        )

    def show_context_menu(self, position: QPoint) -> None:
        """Render current canvas commands at one canvas-local position."""

        menu = QFluentMenuRenderer(parent=self._canvas).render(self.create_model())
        menu.exec(
            self._canvas.mapToGlobal(position),
            aniType=MenuAnimationType.DROP_DOWN,
        )

    def _active_editable_mask_id(self) -> UUID | None:
        """Return the active mask only while it belongs to the current composition."""

        active_mask_id = self._active_mask_id_provider()
        if active_mask_id is None:
            return None
        return (
            active_mask_id
            if any(
                layer.mask_id == active_mask_id
                for layer in self._mask_layers_provider()
            )
            else None
        )

    def _coverage_callback(
        self,
        mask_id: UUID | None,
    ) -> Callable[[], None] | None:
        """Bind one opening's validated mask identity to its edit request."""

        if mask_id is None:
            return None

        def request() -> None:
            """Begin coverage editing for the validated active mask."""

            self._coverage_edit_requested(mask_id)

        return request

    def _dock_callback(self) -> None:
        """Publish one host-owned dock or redock request."""

        self._dock_requested()


__all__ = ["InputCanvasContextMenuController"]
