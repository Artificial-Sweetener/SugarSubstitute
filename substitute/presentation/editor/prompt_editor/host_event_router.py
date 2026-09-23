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

"""Route prompt-editor host events to their focused interaction owners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QContextMenuEvent, QFocusEvent, QKeyEvent, QMouseEvent


@dataclass(frozen=True, slots=True)
class PromptEditorHostEventBindings:
    """Declare the complete host event-routing boundary."""

    surface: QObject
    shell_viewport: QObject
    content_viewport: QObject
    handle_focus_in: Callable[[], None]
    schedule_focus_out_cleanup: Callable[[Qt.FocusReason], None]
    handle_key_press: Callable[[QKeyEvent], None]
    handle_key_release: Callable[[QKeyEvent], None]
    handle_chrome_event: Callable[[QObject, QEvent], bool | None]
    record_context_menu_press: Callable[[], None]
    forward_context_menu: Callable[[QContextMenuEvent], bool]


@dataclass(frozen=True, slots=True)
class PromptEditorHostEventRouter:
    """Own event precedence across projection, chrome, and context menus."""

    bindings: PromptEditorHostEventBindings

    def route(self, watched: QObject, event: QEvent) -> bool | None:
        """Route one event or return ``None`` for QFluent fallback handling."""

        if watched is self.bindings.surface:
            surface_result = self._route_surface_event(event)
            if surface_result is not None:
                return surface_result
        chrome_result = self.bindings.handle_chrome_event(watched, event)
        if chrome_result is not None:
            return chrome_result
        if watched in {
            self.bindings.shell_viewport,
            self.bindings.content_viewport,
        }:
            return self._route_viewport_event(event)
        return None

    def _route_surface_event(self, event: QEvent) -> bool | None:
        """Route focus and keyboard events emitted by the projection surface."""

        if event.type() == QEvent.Type.FocusIn:
            self.bindings.handle_focus_in()
            return False
        if event.type() == QEvent.Type.FocusOut:
            self.bindings.schedule_focus_out_cleanup(cast(QFocusEvent, event).reason())
            return False
        if event.type() == QEvent.Type.KeyPress:
            self.bindings.handle_key_press(cast(QKeyEvent, event))
            return True
        if event.type() == QEvent.Type.KeyRelease:
            self.bindings.handle_key_release(cast(QKeyEvent, event))
            return True
        return None

    def _route_viewport_event(self, event: QEvent) -> bool | None:
        """Route context-menu gestures emitted by either editor viewport."""

        if event.type() == QEvent.Type.MouseButtonPress:
            mouse_event = cast(QMouseEvent, event)
            if mouse_event.button() == Qt.MouseButton.RightButton:
                self.bindings.record_context_menu_press()
        if event.type() == QEvent.Type.ContextMenu:
            return self.bindings.forward_context_menu(cast(QContextMenuEvent, event))
        return None


__all__ = [
    "PromptEditorHostEventBindings",
    "PromptEditorHostEventRouter",
]
