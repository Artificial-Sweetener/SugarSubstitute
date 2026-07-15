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

"""Attach Output generation controls to a floating canvas window."""

from __future__ import annotations

from typing import Any, cast
from weakref import WeakSet

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtWidgets import QWidget

from substitute.application.workspace_state import FloatingCanvasWindowSnapshot
from substitute.presentation.shell.generation_progress_strip import (
    GenerationProgressStrip,
)
from substitute.presentation.shell.generation_progress_strip_registry import (
    GenerationProgressStripRegistry,
)
from substitute.presentation.shell.generation_titlebar_control_registry import (
    GenerationTitleBarControlRegistry,
)
from substitute.presentation.shell.titlebar_buttons import GenerationClusterRevealHost
from substitute.presentation.shell.window_frame import ShellBackdropMode


class OutputFloatingChromeFactory:
    """Create Output-owned floating chrome with shared generation registries."""

    def __init__(
        self,
        *,
        titlebar_control_registry: GenerationTitleBarControlRegistry | None = None,
        progress_strip_registry: GenerationProgressStripRegistry | None = None,
    ) -> None:
        """Store registries used by floating Output canvas chrome."""

        self.titlebar_control_registry = titlebar_control_registry
        self.progress_strip_registry = progress_strip_registry
        self._chrome_instances: WeakSet[OutputFloatingChrome] = WeakSet()

    def __call__(self) -> "OutputFloatingChrome":
        """Return one floating chrome instance for one Output window."""

        chrome = OutputFloatingChrome(
            titlebar_control_registry=self.titlebar_control_registry,
            progress_strip_registry=self.progress_strip_registry,
        )
        self._chrome_instances.add(chrome)
        return chrome

    def set_titlebar_control_registry(
        self,
        registry: GenerationTitleBarControlRegistry,
    ) -> None:
        """Update the registry used for future floating Output windows."""

        self.titlebar_control_registry = registry
        for chrome in tuple(self._chrome_instances):
            chrome.set_titlebar_control_registry(registry)

    def set_progress_strip_registry(
        self,
        registry: GenerationProgressStripRegistry,
    ) -> None:
        """Update the registry used for future floating Output windows."""

        self.progress_strip_registry = registry
        for chrome in tuple(self._chrome_instances):
            chrome.set_progress_strip_registry(registry)


class OutputFloatingChrome:
    """Own Output generation controls installed into a floating host window."""

    def __init__(
        self,
        *,
        titlebar_control_registry: GenerationTitleBarControlRegistry | None,
        progress_strip_registry: GenerationProgressStripRegistry | None,
    ) -> None:
        """Store shared generation registries."""

        self._titlebar_control_registry = titlebar_control_registry
        self._progress_strip_registry = progress_strip_registry
        self._window: object | None = None
        self.generation_reveal_host: GenerationClusterRevealHost | None = None
        self.generation_progress_strip: GenerationProgressStrip | None = None
        self._progress_visibility_connected = False

    def install(self, window: object) -> None:
        """Install Output generation controls into a floating canvas window."""

        self._window = window
        self._install_generation_reveal_host(window)
        self._install_generation_progress_strip(window)

    def on_window_resized(self, window: object) -> None:
        """Keep the Output progress strip aligned with the floating window."""

        self._position_generation_progress_strip(window)

    def event_filter(self, window: object, watched: object, event: QEvent) -> bool:
        """Keep overlay geometry synced as revealed titlebar controls animate."""

        if watched is self.generation_reveal_host and event.type() in {
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.LayoutRequest,
            QEvent.Type.Show,
            QEvent.Type.Hide,
        }:
            self._position_generation_progress_strip(window)
        return False

    def capture_snapshot(
        self,
        snapshot: FloatingCanvasWindowSnapshot,
    ) -> FloatingCanvasWindowSnapshot:
        """Add Output reveal state to the generic floating snapshot."""

        return FloatingCanvasWindowSnapshot(
            label=snapshot.label,
            geometry=snapshot.geometry,
            window_display_state=snapshot.window_display_state,
            output_generation_controls_revealed=self.controls_revealed(),
        )

    def restore_snapshot(self, snapshot: FloatingCanvasWindowSnapshot) -> None:
        """Restore Output reveal state without animation."""

        self.set_controls_revealed(
            snapshot.output_generation_controls_revealed,
            animated=False,
        )

    def dispose(self, _window: object) -> None:
        """Unregister Output floating controls before close or redock."""

        self._unregister_generation_progress_strip()
        self._unregister_generation_reveal_host()
        self._window = None

    def controls_revealed(self) -> bool:
        """Return whether Output generation controls are revealed."""

        host = self.generation_reveal_host
        return host is not None and host.is_expanded()

    def set_controls_revealed(
        self,
        revealed: bool,
        *,
        animated: bool = False,
    ) -> None:
        """Reveal or hide Output generation controls."""

        host = self.generation_reveal_host
        if host is not None:
            host.set_expanded(revealed, animated=animated)

    def set_titlebar_control_registry(
        self,
        registry: GenerationTitleBarControlRegistry,
    ) -> None:
        """Attach or replace the Output titlebar-control registry."""

        self._titlebar_control_registry = registry
        if self._window is not None:
            self._install_generation_reveal_host(self._window)

    def set_progress_strip_registry(
        self,
        registry: GenerationProgressStripRegistry,
    ) -> None:
        """Attach or replace the Output progress-strip registry."""

        self._progress_strip_registry = registry
        if self._window is not None:
            self._install_generation_progress_strip(self._window)

    def _install_generation_reveal_host(self, window: Any) -> None:
        """Install the Output generation reveal host when available."""

        registry = self._titlebar_control_registry
        if registry is None or self.generation_reveal_host is not None:
            return
        title_bar = window.titleBar
        host = GenerationClusterRevealHost(
            title_bar,
            acrylic_style_enabled=(
                getattr(window, "backdrop_mode", None) is ShellBackdropMode.ACRYLIC
            ),
        )
        titlebar_layout = title_bar.layout()
        min_button = getattr(title_bar, "minBtn", None)
        insert_index = titlebar_layout.indexOf(min_button) if min_button else -1
        if insert_index >= 0:
            titlebar_layout.insertWidget(insert_index, host)
        else:
            titlebar_layout.addWidget(host)
        install_event_filter = getattr(host, "installEventFilter", None)
        if callable(install_event_filter):
            install_event_filter(window)
        registry.register(host.control)
        self.generation_reveal_host = host
        self._connect_generation_progress_visibility_refresh(window)

    def _install_generation_progress_strip(self, window: object) -> None:
        """Install the Output progress strip when a registry is available."""

        registry = self._progress_strip_registry
        if registry is None or self.generation_progress_strip is not None:
            return
        strip = GenerationProgressStrip(cast(QWidget, window))
        strip.hide()
        registry.register(
            strip,
            visible_gate=self._generation_progress_visible_gate,
        )
        self.generation_progress_strip = strip
        self._position_generation_progress_strip(window)
        self._connect_generation_progress_visibility_refresh(window)

    def _position_generation_progress_strip(self, window: object) -> None:
        """Overlay the Output progress strip across the floating window top."""

        strip = self.generation_progress_strip
        if strip is None:
            return
        width = self._overlay_width(window)
        strip_height = int(getattr(strip, "strip_height", 6))
        strip.setGeometry(0, 0, width, strip_height)
        strip.raise_()

    def _overlay_width(self, window: object) -> int:
        """Return the floating-window width available before titlebar controls."""

        width = getattr(window, "width", None)
        if callable(width):
            window_width = int(width())
        else:
            rect = getattr(window, "rect", None)
            rect_value = rect() if callable(rect) else None
            rect_width = getattr(rect_value, "width", None)
            window_width = int(rect_width()) if callable(rect_width) else 0
        controls_start_x = self._progress_controls_start_x(window)
        if controls_start_x is None:
            return window_width
        return max(0, min(window_width, controls_start_x))

    def _progress_controls_start_x(self, window: object) -> int | None:
        """Return the left edge of controls the progress strip must avoid."""

        host = self.generation_reveal_host
        if host is None:
            return None
        control = getattr(host, "control", None)
        stop_target = None
        progress_stop_target = getattr(control, "progress_strip_stop_target", None)
        if callable(progress_stop_target):
            stop_target = progress_stop_target()
        if stop_target is None:
            stop_target = getattr(control, "_batch_accessory", None) or control
        if stop_target is None:
            return None
        return self._widget_left_edge_in_window(window, stop_target)

    @staticmethod
    def _widget_left_edge_in_window(window: object, widget: object) -> int | None:
        """Map a child widget's left edge into floating-window coordinates."""

        map_to = getattr(widget, "mapTo", None)
        if callable(map_to):
            try:
                point = map_to(window, QPoint(0, 0))
            except TypeError:
                point = None
            if point is not None:
                point_x = getattr(point, "x", None)
                if callable(point_x):
                    return int(point_x())
        x = getattr(widget, "x", None)
        if callable(x):
            return int(x())
        return None

    def _generation_progress_visible_gate(self) -> bool:
        """Return whether local reveal state allows the progress strip to show."""

        host = self.generation_reveal_host
        return host is not None and host.is_expanded()

    def _connect_generation_progress_visibility_refresh(self, window: object) -> None:
        """Refresh progress-strip visibility when reveal state changes."""

        if self._progress_visibility_connected:
            return
        host = self.generation_reveal_host
        if host is None:
            return
        expanded_changed = getattr(host, "expandedChanged", None)
        connect = getattr(expanded_changed, "connect", None)
        if not callable(connect):
            return

        def refresh_visibility(_expanded: bool) -> None:
            """Reposition Output progress chrome after floating layout changes."""

            registry = self._progress_strip_registry
            strip = self.generation_progress_strip
            if registry is not None and strip is not None:
                self._position_generation_progress_strip(window)
                registry.refresh_visibility(strip)
            emit_layout_changed = getattr(
                getattr(window, "layoutStateChanged", None),
                "emit",
                None,
            )
            if callable(emit_layout_changed):
                emit_layout_changed()

        connect(refresh_visibility)
        self._progress_visibility_connected = True

    def _unregister_generation_reveal_host(self) -> None:
        """Unregister the Output generation control."""

        registry = self._titlebar_control_registry
        host = self.generation_reveal_host
        if registry is None or host is None:
            return
        registry.unregister(host.control)
        self._titlebar_control_registry = None

    def _unregister_generation_progress_strip(self) -> None:
        """Unregister the Output progress strip."""

        registry = self._progress_strip_registry
        strip = self.generation_progress_strip
        if registry is None or strip is None:
            return
        registry.unregister(strip)
        self._progress_strip_registry = None


__all__ = [
    "OutputFloatingChrome",
    "OutputFloatingChromeFactory",
]
