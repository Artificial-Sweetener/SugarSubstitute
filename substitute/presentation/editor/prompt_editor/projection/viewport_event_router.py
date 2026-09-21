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

"""Own projection viewport event arbitration across interaction controllers."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from ..interactions import (
    PromptExternalTextInputOwner,
    PromptSurfaceMouseHandler,
    PromptSurfaceWheelHandler,
    PromptWheelScrollResult,
)
from .edit_to_frame import PromptLayoutEditToFrameCoordinator


class PromptProjectionViewportEventRouter(QObject):
    """Route viewport events to the controller that authoritatively owns them."""

    def __init__(
        self,
        *,
        viewport: QWidget,
        layout: PromptLayoutEditToFrameCoordinator,
        mouse: PromptSurfaceMouseHandler,
        wheel: PromptSurfaceWheelHandler,
        external_text: PromptExternalTextInputOwner,
        parent: QObject,
    ) -> None:
        """Bind the mounted viewport and its focused interaction controllers."""

        super().__init__(parent)
        self._viewport = viewport
        self._layout = layout
        self._mouse = mouse
        self._wheel = wheel
        self._external_text = external_text

    def handle_viewport_event(self, event: QEvent) -> bool | None:
        """Handle target-side hover and external-input events before Qt fallback."""

        event_type = event.type()
        if event_type == QEvent.Type.MouseMove:
            self._mouse.update_hovered_token(cast(QMouseEvent, event).position())
        elif event_type == QEvent.Type.DragEnter:
            self._external_text.accept_or_ignore_drag(cast(QDragEnterEvent, event))
            return True
        elif event_type == QEvent.Type.DragMove:
            self._external_text.accept_or_ignore_drag(cast(QDragMoveEvent, event))
            return True
        elif event_type == QEvent.Type.Drop:
            drop_event = cast(QDropEvent, event)
            self._external_text.drop(
                drop_event,
                viewport_position=drop_event.position().toPoint(),
            )
            return True
        elif event_type == QEvent.Type.Leave:
            self._clear_pointer_state()
        return None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Handle events delivered directly to the mounted inner viewport."""

        if watched is not self._viewport:
            return False
        event_type = event.type()
        if event_type == QEvent.Type.DragEnter:
            self._external_text.accept_or_ignore_drag(cast(QDragEnterEvent, event))
            return True
        if event_type == QEvent.Type.DragMove:
            self._external_text.accept_or_ignore_drag(cast(QDragMoveEvent, event))
            return True
        if event_type == QEvent.Type.Drop:
            drop_event = cast(QDropEvent, event)
            self._external_text.drop(
                drop_event,
                viewport_position=drop_event.position().toPoint(),
            )
            return True
        if event_type == QEvent.Type.MouseButtonPress:
            mouse_event = cast(QMouseEvent, event)
            return self._mouse.handle_viewport_mouse_press(
                mouse_event,
                self._layout.frame,
                viewport_position=mouse_event.position(),
            )
        if event_type == QEvent.Type.MouseMove:
            mouse_event = cast(QMouseEvent, event)
            return self._mouse.handle_viewport_mouse_move(
                mouse_event,
                self._layout.frame,
                viewport_position=mouse_event.position(),
            )
        if event_type == QEvent.Type.MouseButtonRelease:
            return self._mouse.handle_viewport_mouse_release(cast(QMouseEvent, event))
        if event_type == QEvent.Type.MouseButtonDblClick:
            mouse_event = cast(QMouseEvent, event)
            return self._mouse.handle_viewport_mouse_double_click(
                mouse_event,
                self._layout.frame,
                viewport_position=mouse_event.position(),
            )
        if event_type == QEvent.Type.Wheel:
            wheel_event = cast(QWheelEvent, event)
            self._mouse.update_hovered_token(wheel_event.position())
            result = self._wheel.handle_prompt_wheel_scroll(wheel_event)
            if result is PromptWheelScrollResult.CONSUMED:
                wheel_event.accept()
                return True
            wheel_event.ignore()
            return False
        if event_type == QEvent.Type.Leave:
            self._clear_pointer_state()
        return False

    def _clear_pointer_state(self) -> None:
        """Clear hover and wheel spill state before repainting the viewport."""

        self._mouse.clear_hovered_token(update=False)
        self._wheel.clear_boundary_spill()
        self._viewport.update()


__all__ = ["PromptProjectionViewportEventRouter"]
