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

"""Compose selectable, dockable canvas pages under one authoritative host."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.workspace_state import CanvasLayoutSnapshot
from substitute.presentation.canvas.host.canvas_docking_controller import (
    CanvasDockingController,
)
from substitute.presentation.canvas.host.canvas_host_chrome import CanvasHostChrome
from substitute.presentation.canvas.host.canvas_host_selector import CanvasHostSelector
from substitute.presentation.canvas.host.canvas_host_stack import (
    CanvasHostStack,
    create_canvas_host_entry,
)
from substitute.presentation.canvas.host.canvas_host_state import (
    CanvasHostEntry,
    CanvasHostPage,
    CanvasHostState,
)


class CanvasHost(QWidget):
    """Render and coordinate the shell's configured canvas pages."""

    visibility_changed = Signal(bool)
    layout_state_changed = Signal()
    canvas_activated = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        pages: Sequence[CanvasHostPage] = (),
    ) -> None:
        """Create the stack, selector overlay, and docking lifecycle."""

        super().__init__(parent)
        self.resize(1000, 700)
        entries = tuple(create_canvas_host_entry(page) for page in pages)
        self._state = CanvasHostState(entries)
        self._stack = CanvasHostStack()

        self.canvas_region = QWidget(self)
        self.canvas_region.setObjectName("canvas_region")
        canvas_layout = QVBoxLayout(self.canvas_region)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        canvas_layout.addLayout(self._stack.layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.canvas_region)

        self._chrome = CanvasHostChrome(
            self.canvas_region,
            selected_callback=self.focus_attached_canvas,
        )
        self._docking = CanvasDockingController(
            host=self,
            state=self._state,
            stack=self._stack,
            synchronize_presentation=self._synchronize_presentation,
            visibility_changed=self.visibility_changed.emit,
            layout_state_changed=self.layout_state_changed.emit,
            canvas_activated=self.canvas_activated.emit,
        )
        self._connect_canvas_actions()
        self.setStyleSheet(
            "QWidget#canvas_region { border: none; background-color: transparent; }"
        )
        self._synchronize_presentation()
        self._apply_initial_availability()
        self.window().destroyed.connect(self._docking.close_all)

    @property
    def selector(self) -> CanvasHostSelector:
        """Return the host selector surface for rendering and interaction tests."""

        return self._chrome.selector

    def canvas_for(self, route_key: str) -> QWidget | None:
        """Return the configured canvas widget for a route key."""

        entry = self._state.entry(route_key)
        return entry.page.widget if entry is not None else None

    def canvases(self) -> tuple[QWidget, ...]:
        """Return configured canvas widgets in authoritative display order."""

        return tuple(entry.page.widget for entry in self._state)

    def focus_attached_canvas(self, route_key: str) -> None:
        """Select one attached available canvas without affecting windows."""

        entry = self._state.entry(route_key)
        if entry is None or not entry.selectable:
            return
        self._state.select(route_key)
        self._synchronize_presentation()
        self.canvas_activated.emit(route_key)

    def set_canvas_available(
        self,
        route_key: str,
        available: bool,
        *,
        reason: ApplicationText = "",
        fallback_route_key: str | None = None,
    ) -> None:
        """Apply availability to host state and the canvas's passive surface."""

        entry = self._state.entry(route_key)
        if entry is None:
            return
        fallback_route_key = fallback_route_key or entry.page.fallback_route_key
        self._state.set_available(
            route_key,
            available,
            fallback_route_key=fallback_route_key,
        )
        self._apply_canvas_availability(entry, available, reason)
        self._synchronize_presentation()

    def is_canvas_visible(self, route_key: str) -> bool:
        """Return whether a canvas is the docked selection or a visible window."""

        entry = self._state.entry(route_key)
        if entry is None:
            return False
        if entry.floating_window is not None:
            return bool(entry.floating_window.isVisible())
        return entry.selectable and self._state.active_route_key == route_key

    def handle_canvas_dock_action(self, route_key: str) -> None:
        """Toggle attachment from a canvas-owned context-menu action."""

        self._docking.toggle_attachment(route_key)

    def detach_canvas(self, route_key: str) -> None:
        """Detach a configured canvas into a floating window."""

        self._docking.detach(route_key)

    def canvas_layout_snapshot(self) -> CanvasLayoutSnapshot:
        """Return restorable floating state for configured canvases."""

        return self._docking.canvas_layout_snapshot()

    def apply_restored_canvas_layout(
        self,
        snapshot: CanvasLayoutSnapshot | None,
    ) -> None:
        """Restore floating state through the docking lifecycle owner."""

        self._docking.apply_restored_layout(snapshot)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep selector geometry and canvas-owned chrome synchronized."""

        super().resizeEvent(event)
        self._chrome.synchronize(self._state)

    def closeEvent(self, event: Any) -> None:
        """Close floating canvases without redocking during host teardown."""

        self._docking.close_all()
        event.accept()

    def _synchronize_presentation(self) -> None:
        """Project authoritative host state into stack and chrome views."""

        self._stack.synchronize(self._state)
        self._chrome.synchronize(self._state)

    def _connect_canvas_actions(self) -> None:
        """Route each canvas's dock action into the shared docking owner once."""

        for entry in self._state:
            signal = getattr(entry.page.widget, "dockActionRequested", None)
            connect = getattr(signal, "connect", None)
            if callable(connect):
                connect(
                    lambda *args, route_key=entry.route_key: (
                        self.handle_canvas_dock_action(route_key)
                    )
                )

    def _apply_initial_availability(self) -> None:
        """Project configured unavailable state into canvas-owned surfaces."""

        for entry in self._state:
            if not entry.available:
                self._apply_canvas_availability(
                    entry,
                    False,
                    entry.page.unavailable_reason,
                )

    @staticmethod
    def _apply_canvas_availability(
        entry: CanvasHostEntry,
        available: bool,
        reason: ApplicationText,
    ) -> None:
        """Apply host availability through an optional canvas presentation port."""

        set_available = getattr(entry.page.widget, "set_available", None)
        if callable(set_available):
            set_available(available, reason)


def build_canvas_host(
    *,
    pages: Sequence[CanvasHostPage],
    parent: QWidget | None = None,
) -> CanvasHost:
    """Build a generic canvas host for already-created canvas pages."""

    return CanvasHost(parent=parent, pages=pages)


__all__ = ["CanvasHost", "build_canvas_host"]
