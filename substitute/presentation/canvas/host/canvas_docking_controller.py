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

"""Coordinate canvas detachment, floating windows, redocking, and persistence."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    render_application_text,
    set_localized_window_title,
)

from substitute.application.workspace_state import CanvasLayoutSnapshot
from substitute.presentation.canvas.host.canvas_host_stack import CanvasHostStack
from substitute.presentation.canvas.host.canvas_host_state import (
    CanvasHostEntry,
    CanvasHostState,
)
from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasWindow,
)
from substitute.shared.logging.logger import get_logger, log_exception, log_info

_LOGGER = get_logger("presentation.canvas.host.canvas_docking_controller")


class CanvasDockingController:
    """Own floating-window transitions for authoritative canvas host entries."""

    def __init__(
        self,
        *,
        host: QWidget,
        state: CanvasHostState,
        stack: CanvasHostStack,
        synchronize_presentation: Callable[[], None],
        visibility_changed: Callable[[bool], None],
        layout_state_changed: Callable[[], None],
        canvas_activated: Callable[[str], None],
    ) -> None:
        """Bind docking transitions to host state, presentation, and signals."""

        self._host = host
        self._state = state
        self._stack = stack
        self._synchronize_presentation = synchronize_presentation
        self._visibility_changed = visibility_changed
        self._layout_state_changed = layout_state_changed
        self._canvas_activated = canvas_activated
        self._closing = False
        for entry in self._state:
            self._set_canvas_detached(entry, False)

    def toggle_attachment(self, route_key: str) -> None:
        """Toggle one configured canvas between the docked host and a window."""

        entry = self._state.entry(route_key)
        if entry is None:
            return
        if entry.floating_window is None:
            self.detach(route_key)
        else:
            self.redock(route_key)

    def detach(self, route_key: str) -> None:
        """Move one selectable canvas into a standalone floating window."""

        entry = self._state.entry(route_key)
        if (
            entry is None
            or entry.floating_window is not None
            or not self._stack.contains(entry)
            or not self._state.prepare_detach(route_key)
        ):
            return

        self._stack.layout.removeWidget(entry.wrapper)
        entry.page.widget.setParent(None)
        try:
            floating_window = self._create_floating_window(entry)
        except Exception:
            wrapper_layout = entry.wrapper.layout()
            if isinstance(wrapper_layout, QVBoxLayout):
                wrapper_layout.addWidget(entry.page.widget)
            self._state.select(route_key)
            self._synchronize_presentation()
            log_exception(
                _LOGGER,
                "Failed to create floating canvas window",
                route_key=route_key,
            )
            raise
        self._state.complete_detach(route_key, floating_window)
        self._set_canvas_detached(entry, True)
        self._synchronize_presentation()

        floating_window.resize(800, 600)
        floating_window.show()
        self._canvas_activated(route_key)
        if not self._state.selectable_entries():
            self._visibility_changed(False)
        self._layout_state_changed()
        log_info(_LOGGER, "Detached canvas into floating window", route_key=route_key)

    def redock(self, route_key: str) -> None:
        """Close a floating canvas window through its normal redock callback."""

        entry = self._state.entry(route_key)
        if entry is None or entry.floating_window is None:
            return
        entry.floating_window.close()

    def canvas_layout_snapshot(self) -> CanvasLayoutSnapshot:
        """Capture floating canvas state in authoritative page order."""

        snapshots = tuple(
            entry.floating_window.floating_canvas_snapshot()
            for entry in self._state
            if entry.floating_window is not None
        )
        return CanvasLayoutSnapshot(floating_windows=snapshots)

    def apply_restored_layout(self, snapshot: CanvasLayoutSnapshot | None) -> None:
        """Restore configured floating canvases and their window geometry."""

        if snapshot is None:
            return
        snapshots_by_route = {
            floating_snapshot.label: floating_snapshot
            for floating_snapshot in snapshot.floating_windows
            if self._state.entry(floating_snapshot.label) is not None
        }
        for entry in self._state:
            should_float = entry.route_key in snapshots_by_route
            if should_float and entry.floating_window is None:
                self.detach(entry.route_key)
            elif not should_float and entry.floating_window is not None:
                self.redock(entry.route_key)

        for route_key, floating_snapshot in snapshots_by_route.items():
            entry = self._state.require_entry(route_key)
            if entry.floating_window is not None:
                entry.floating_window.apply_restored_floating_snapshot(
                    floating_snapshot
                )

    def close_all(self) -> None:
        """Close every floating window without redocking during host teardown."""

        self._closing = True
        for entry in self._state:
            floating_window = entry.floating_window
            if floating_window is None:
                continue
            self._state.release_floating_window(entry.route_key, floating_window)
            floating_window.close()

    def _create_floating_window(self, entry: CanvasHostEntry) -> FloatingCanvasWindow:
        """Create and configure the floating window for one canvas entry."""

        chrome_factory = entry.page.floating_chrome_factory
        floating_window = FloatingCanvasWindow(
            entry.page.widget,
            entry.route_key,
            self._redock_callback,
            backdrop_mode=getattr(self._host.window(), "_backdrop_mode", None),
            floating_chrome=chrome_factory() if chrome_factory is not None else None,
        )
        floating_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        floating_window.setWindowFlag(Qt.WindowType.Window, True)
        floating_window.setWindowFlag(Qt.WindowType.Tool, False)
        floating_window.setWindowModality(Qt.WindowModality.NonModal)
        if isinstance(floating_window, QObject):
            set_localized_window_title(
                floating_window,
                "%1 Canvas",
                entry.page.title,
            )
        else:
            floating_window.setWindowTitle(
                render_application_text(app_text("%1 Canvas", entry.page.title))
            )
        floating_window.setWindowIcon(self._host.window().windowIcon())
        floating_window.layoutStateChanged.connect(self._layout_state_changed)
        floating_window.destroyed.connect(
            partial(
                self._floating_window_destroyed,
                entry.route_key,
                floating_window,
            )
        )
        return floating_window

    def _floating_window_destroyed(
        self,
        route_key: str,
        floating_window: FloatingCanvasWindow,
        _destroyed_object: object | None = None,
    ) -> None:
        """Release a Qt-deleted window that could no longer redock normally."""

        if not self._state.release_floating_window(route_key, floating_window):
            return
        self._layout_state_changed()

    def _redock_callback(self, widget: QWidget, route_key: str) -> None:
        """Restore one closed floating window into its authoritative entry."""

        if self._closing:
            return
        entry = self._state.entry(route_key)
        if entry is None or widget is not entry.page.widget:
            return
        wrapper_layout = entry.wrapper.layout()
        if isinstance(wrapper_layout, QVBoxLayout):
            wrapper_layout.addWidget(widget)
        self._set_canvas_detached(entry, False)
        activated = self._state.complete_attach(route_key)
        self._synchronize_presentation()
        self._visibility_changed(True)
        if activated:
            self._canvas_activated(route_key)
        self._layout_state_changed()
        log_info(_LOGGER, "Redocked floating canvas", route_key=route_key)

    @staticmethod
    def _set_canvas_detached(entry: CanvasHostEntry, detached: bool) -> None:
        """Project host attachment into canvas-owned context menu state."""

        set_canvas_detached = getattr(entry.page.widget, "set_canvas_detached", None)
        if callable(set_canvas_detached):
            set_canvas_detached(detached)


__all__ = ["CanvasDockingController"]
