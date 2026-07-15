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

"""Host one undocked canvas widget in a standalone floating window."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qframelesswindow import AcrylicWindow  # type: ignore[import-untyped]

from substitute.application.workspace_state import FloatingCanvasWindowSnapshot
from substitute.presentation.canvas.host.floating_canvas_snapshot import (
    apply_restored_floating_snapshot,
    floating_canvas_snapshot,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
    apply_acrylic_effect,
    apply_shell_titlebar_button_theme,
)

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


class FloatingCanvasChrome(Protocol):
    """Describe optional domain-owned chrome for one floating canvas window."""

    def install(self, window: "FloatingCanvasWindow") -> None:
        """Install domain-specific floating chrome into the window."""

    def on_window_resized(self, window: "FloatingCanvasWindow") -> None:
        """Update chrome geometry after the floating window is resized."""

    def event_filter(
        self,
        window: "FloatingCanvasWindow",
        watched: object,
        event: QEvent,
    ) -> bool:
        """Handle event-filter updates for chrome-owned widgets."""

    def capture_snapshot(
        self,
        snapshot: FloatingCanvasWindowSnapshot,
    ) -> FloatingCanvasWindowSnapshot:
        """Return snapshot state enriched with chrome-owned durable state."""

    def restore_snapshot(self, snapshot: FloatingCanvasWindowSnapshot) -> None:
        """Restore chrome-owned durable state from a snapshot."""

    def dispose(self, window: "FloatingCanvasWindow") -> None:
        """Detach chrome before the floating window closes or redocks."""


class FloatingCanvasWindow(AcrylicWindow):  # type: ignore[misc]
    """Host one undocked canvas widget in a standalone acrylic window."""

    layoutStateChanged = Signal()

    def __init__(
        self,
        canvas_widget: QWidget,
        label: str,
        redock_callback: Callable[[QWidget, str], None],
        *,
        backdrop_mode: ShellBackdropMode | None = ShellBackdropMode.MICA,
        floating_chrome: FloatingCanvasChrome | None = None,
    ) -> None:
        """Create floating shell window and keep content geometry in sync."""

        super().__init__()
        self.canvas_widget = canvas_widget
        self.label = label
        self.redock_callback = redock_callback
        self._backdrop_mode = backdrop_mode
        self._floating_chrome = floating_chrome

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._content_layout = layout
        layout.addWidget(self.canvas_widget)
        content.setGeometry(self.rect())
        content.setParent(self)
        self.titleBar.raise_()
        self._content = content
        self.resizeEvent = self._resize_event_hook
        self.setWindowTitle(f"{label}")
        if self._backdrop_mode is ShellBackdropMode.ACRYLIC:
            apply_acrylic_effect(self)
        elif self._backdrop_mode is not None:
            self.windowEffect.setMicaEffect(
                self.winId(),
                isDarkMode=isDarkTheme(),
                isAlt=self._backdrop_mode is ShellBackdropMode.MICA_ALT,
            )
        if self._floating_chrome is not None:
            self._floating_chrome.install(self)
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

    @property
    def backdrop_mode(self) -> ShellBackdropMode | None:
        """Return the floating shell backdrop mode."""

        return self._backdrop_mode

    @property
    def floating_chrome(self) -> FloatingCanvasChrome | None:
        """Return optional domain-owned chrome attached to this floating window."""

        return self._floating_chrome

    def _resize_event_hook(self, event: object) -> None:
        """Keep child content geometry aligned with floating window bounds."""

        super().resizeEvent(event)
        if hasattr(self, "_content"):
            self._content.setGeometry(self.rect())
        if self._floating_chrome is not None:
            self._floating_chrome.on_window_resized(self)
        self.layoutStateChanged.emit()

    def moveEvent(self, event: object) -> None:
        """Emit durable-layout changes when the user moves this window."""

        super().moveEvent(event)
        self.layoutStateChanged.emit()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        """Delegate optional floating-chrome filter work to its owner."""

        if self._floating_chrome is not None and self._floating_chrome.event_filter(
            self,
            watched,
            event,
        ):
            return True
        return bool(super().eventFilter(watched, event))

    def _apply_theme_styles(self) -> None:
        """Reapply shell titlebar button colors after theme changes."""

        apply_shell_titlebar_button_theme(self.titleBar)

    def floating_canvas_snapshot(self) -> FloatingCanvasWindowSnapshot:
        """Return restorable state for this floating canvas window."""

        return floating_canvas_snapshot(
            self,
            chrome=getattr(self, "_floating_chrome", None),
        )

    def apply_restored_floating_snapshot(
        self,
        snapshot: FloatingCanvasWindowSnapshot,
    ) -> None:
        """Apply restorable geometry and display state to this floating window."""

        apply_restored_floating_snapshot(
            self,
            snapshot,
            chrome=getattr(self, "_floating_chrome", None),
        )

    def closeEvent(self, event: Any) -> None:
        """Redock widget back into tab host unless parent manager is closing."""

        floating_chrome = getattr(self, "_floating_chrome", None)
        if floating_chrome is not None:
            floating_chrome.dispose(self)
        if not getattr(self.parent(), "closing", False):
            self.redock_callback(self.canvas_widget, self.label)
        event.accept()


__all__ = [
    "FloatingCanvasChrome",
    "FloatingCanvasWindow",
]
