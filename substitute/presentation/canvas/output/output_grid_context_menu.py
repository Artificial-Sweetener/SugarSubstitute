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

"""Render addressed Output actions for one CuteCanvas grid target."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtWidgets import QWidget
from cutecanvas import CanvasContentReference, DragSubject
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    MenuAnimationType,
)
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer


@dataclass(frozen=True, slots=True, weakref_slot=True)
class OutputGridContextMenu:
    """Own the target-addressed actions available from an Output grid tile."""

    parent: QWidget
    request_copy: Callable[[CanvasContentReference], None]
    image_id_for_reference: Callable[[CanvasContentReference], UUID | None]
    image_payload: Callable[[UUID], object | None]
    image_metadata: Callable[[UUID], OutputImageMeta | None]
    image_is_authorized: Callable[[UUID], bool]
    open_single_editor: Callable[[object, OutputImageMeta], bool] | None
    canvas_detached: Callable[[], bool]
    request_dock_action: Callable[[], None]

    def show(self, subject: object, global_position: object) -> None:
        """Show actions bound to the target identified by CuteCanvas."""

        reference = self._content_reference(subject)
        if reference is None:
            return
        menu = QFluentMenuRenderer(parent=self.parent).render(
            self.menu_model(reference)
        )
        menu.exec(global_position, aniType=MenuAnimationType.DROP_DOWN)

    def menu_model(self, reference: CanvasContentReference) -> MenuModel:
        """Build actions whose callbacks retain the clicked grid target."""

        return MenuModel(
            entries=(
                MenuItem(
                    "output_canvas.copy",
                    app_text("Copy"),
                    callback=lambda: self.request_copy(reference),
                    icon=FIF.COPY,
                ),
                MenuItem(
                    "output_canvas.open_current_external",
                    app_text("Open in Photoshop"),
                    callback=lambda: self.open_external(reference),
                    icon=FIF.PHOTO,
                ),
                MenuSeparator(),
                MenuItem(
                    "output_canvas.dock_action",
                    app_text(
                        "Redock canvas" if self.canvas_detached() else "Undock canvas"
                    ),
                    callback=self.request_dock_action,
                    icon=(
                        FIF.BACK_TO_WINDOW
                        if self.canvas_detached()
                        else FIF.FULL_SCREEN
                    ),
                ),
            )
        )

    def open_external(self, reference: CanvasContentReference) -> None:
        """Open exactly the authorized grid target in the configured editor."""

        opener = self.open_single_editor
        image_id = self.image_id_for_reference(reference)
        if opener is None or image_id is None or not self.image_is_authorized(image_id):
            return
        image = self.image_payload(image_id)
        metadata = self.image_metadata(image_id)
        if image is not None and metadata is not None:
            opener(image, metadata)

    @staticmethod
    def _content_reference(subject: object) -> CanvasContentReference | None:
        """Extract CuteCanvas's stable reference from its context envelope."""

        if isinstance(subject, CanvasContentReference):
            return subject
        if isinstance(subject, DragSubject) and isinstance(
            subject.subject_id,
            CanvasContentReference,
        ):
            return subject.subject_id
        return None


__all__ = ["OutputGridContextMenu"]
