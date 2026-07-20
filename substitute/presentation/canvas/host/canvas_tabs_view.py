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

"""Render dockable canvas pages and undock/redock behavior."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
    set_localized_window_title,
)

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QStackedLayout, QVBoxLayout, QWidget
from qfluentwidgets import Pivot, PivotItem  # type: ignore[import-untyped]
from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]

from substitute.application.workspace_state import CanvasLayoutSnapshot
from substitute.presentation.canvas.host.canvas_availability_presenter import (
    CanvasAvailabilityPresenter,
)
from substitute.presentation.canvas.host.canvas_focus_controller import (
    CanvasFocusController,
)
from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasChrome,
    FloatingCanvasWindow,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.shell.window_frame import ShellBackdropMode
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("presentation.canvas.host.canvas_tabs_view")

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


FloatingChromeFactory = Callable[[], FloatingCanvasChrome | None]


@dataclass(frozen=True, slots=True)
class CanvasHostPage:
    """Describe one canvas page hosted by the generic canvas shell."""

    route_key: str
    title: ApplicationText
    widget: QWidget
    floating_chrome_factory: FloatingChromeFactory | None = None
    default_available: bool = True
    unavailable_reason: ApplicationText = ""
    fallback_route_key: str | None = None


class DockablePivotItem(PivotItem):  # type: ignore[misc]
    """Pivot item that exposes a double-click signal used for undocking tabs."""

    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event: Any) -> None:
        """Emit custom double-click signal for left-button interactions."""

        if event.button() == Qt.LeftButton:  # type: ignore[attr-defined]
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class CanvasTabManager(QWidget):
    """Render tabbed canvas pages with undock and visibility signaling."""

    visibility_changed = Signal(bool)
    layout_state_changed = Signal()
    canvas_activated = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        pages: Sequence[CanvasHostPage] = (),
    ) -> None:
        """Initialize pivot/stack canvas region and add configured pages."""

        super().__init__(parent)
        set_localized_window_title(self, "Canvas Tab Demo")
        self.resize(1000, 700)

        self.pivot = Pivot()
        self.pivot.currentItemChanged.connect(self.on_pivot_changed)
        self.pivot.setSizePolicy(
            self.pivot.sizePolicy().horizontalPolicy(),
            self.pivot.sizePolicy().verticalPolicy(),
        )
        self.pivot.setVisible(True)
        self._install_pivot_undock_handler()

        self.stack = QStackedLayout()
        self.canvas_map: dict[str, QWidget] = {}
        self.wrapper_map: dict[str, QWidget] = {}
        self.floating_windows: dict[str, FloatingCanvasWindow] = {}
        self._canvas_dock_action_callbacks: dict[str, Callable[..., None]] = {}
        self._canvas_availability: dict[str, bool] = {}
        self._canvas_titles: dict[str, ApplicationText] = {}
        self._floating_chrome_factories: dict[str, FloatingChromeFactory] = {}
        self._fallback_labels: dict[str, str | None] = {}

        for page in pages:
            self._canvas_titles[page.route_key] = page.title
            self._floating_chrome_factories[page.route_key] = (
                page.floating_chrome_factory or _no_floating_chrome
            )
            self._fallback_labels[page.route_key] = page.fallback_route_key
            self._canvas_availability[page.route_key] = page.default_available
            self.add_canvas(page.route_key, page.widget)

        self.stack.setCurrentIndex(0)
        self.pivot.setItemFontSize(14)
        for item in self.pivot.items.values():
            item.setStyleSheet(self._pivot_item_stylesheet())

        self.canvas_region = QWidget()
        self.canvas_region.setObjectName("canvas_region")
        canvas_layout = QVBoxLayout(self.canvas_region)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self.pivot)
        canvas_layout.addLayout(self.stack)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.canvas_region)

        self.setStyleSheet(
            """
            QTabBar {
                border: none;
                background-color: transparent;
            }
            QWidget#canvas_region {
                border: none;
                background-color: transparent;
            }
        """
        )
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)
        self.window().destroyed.connect(self._close_all_floating_windows)

        for page in pages:
            if not page.default_available:
                self.set_canvas_available(
                    page.route_key,
                    False,
                    reason=page.unavailable_reason,
                    fallback_label=page.fallback_route_key,
                )

    def add_canvas(self, label: str, widget: QWidget) -> None:
        """Add canvas widget as dockable pivot tab page."""

        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        pivot_item = CanvasTabManager._pivot_item_for(self, label)
        self.pivot.insertWidget(-1, label, pivot_item)
        self.canvas_map[label] = widget
        self.wrapper_map[label] = wrapper
        CanvasTabManager._set_canvas_detached(self, label, False)
        CanvasTabManager._connect_canvas_dock_action(self, label, widget)
        self.stack.insertWidget(len(self.pivot.items) - 1, wrapper)
        if len(self.pivot.items) == 1:
            self.pivot.setCurrentItem(label)
            self.stack.setCurrentIndex(0)
        self.update_tab_visibility()

    def on_pivot_changed(self, route_key: str) -> None:
        """Switch visible canvas page for selected pivot route key."""

        index = CanvasTabManager._stack_index_for_label(self, route_key)
        if index >= 0:
            self.stack.setCurrentIndex(index)
            emit = getattr(getattr(self, "canvas_activated", None), "emit", None)
            if callable(emit):
                emit(route_key)

    def focus_attached_canvas(self, label: str) -> None:
        """Select one docked canvas tab without affecting detached windows."""

        if CanvasFocusController.focus_attached_canvas(self, label):
            emit = getattr(getattr(self, "canvas_activated", None), "emit", None)
            if callable(emit):
                emit(label)

    def set_canvas_available(
        self,
        label: str,
        available: bool,
        *,
        reason: str = "",
        fallback_label: str | None = None,
    ) -> None:
        """Show or hide one docked canvas selector and update passive state."""

        CanvasAvailabilityPresenter.set_canvas_available(
            self,
            label,
            available,
            reason=reason,
            fallback_label=fallback_label or self._fallback_labels.get(label),
        )

    def is_canvas_visible(self, label: str) -> bool:
        """Return whether a canvas page is visible as docked or floating."""

        output_window = self.floating_windows.get(label)
        if output_window is not None:
            is_visible = getattr(output_window, "isVisible", None)
            return bool(is_visible()) if callable(is_visible) else True
        current_route_key = getattr(self.pivot, "currentRouteKey", None)
        if callable(current_route_key):
            return bool(current_route_key() == label)
        return CanvasTabManager._stack_index_for_label(self, label) >= 0

    def canvas_layout_snapshot(self) -> CanvasLayoutSnapshot:
        """Return restorable docking/floating state for configured canvases."""

        snapshots = []
        for label in self.canvas_map:
            floating_window = self.floating_windows.get(label)
            if floating_window is None:
                continue
            snapshot = getattr(floating_window, "floating_canvas_snapshot", None)
            if callable(snapshot):
                snapshots.append(snapshot())
        return CanvasLayoutSnapshot(floating_windows=tuple(snapshots))

    def apply_restored_canvas_layout(
        self,
        snapshot: CanvasLayoutSnapshot | None,
    ) -> None:
        """Restore canvas docking/floating state from shell layout."""

        if snapshot is None:
            return
        known_labels = set(self.canvas_map)
        snapshots_by_label = {
            floating_snapshot.label: floating_snapshot
            for floating_snapshot in snapshot.floating_windows
            if floating_snapshot.label in known_labels
        }
        for label in tuple(known_labels):
            should_float = label in snapshots_by_label
            is_floating = label in self.floating_windows
            if should_float and not is_floating:
                self.undock_tab(label)
            elif not should_float and is_floating:
                CanvasTabManager._redock_floating_window(self, label)

        for label, floating_snapshot in snapshots_by_label.items():
            floating_window = self.floating_windows.get(label)
            if floating_window is None:
                continue
            apply_snapshot = getattr(
                floating_window,
                "apply_restored_floating_snapshot",
                None,
            )
            if callable(apply_snapshot):
                apply_snapshot(floating_snapshot)

    def handle_canvas_dock_action(self, label: str) -> None:
        """Toggle one canvas attachment state from its context-menu action."""

        if label in self.floating_windows:
            floating_window = self.floating_windows[label]
            close = getattr(floating_window, "close", None)
            if callable(close):
                close()
                return
            redock_callback = getattr(floating_window, "redock_callback", None)
            canvas_widget = getattr(
                floating_window,
                "canvas_widget",
                self.canvas_map.get(label),
            )
            if callable(redock_callback) and canvas_widget is not None:
                redock_callback(canvas_widget, label)
            return
        if label in self.canvas_map:
            self.undock_tab(label)

    def _redock_floating_window(self, label: str) -> None:
        """Redock one floating canvas window through its normal close path."""

        floating_window = self.floating_windows.get(label)
        if floating_window is None:
            return
        close = getattr(floating_window, "close", None)
        if callable(close):
            close()
            return
        redock_callback = getattr(floating_window, "redock_callback", None)
        canvas_widget = getattr(floating_window, "canvas_widget", None)
        if callable(redock_callback) and canvas_widget is not None:
            redock_callback(canvas_widget, label)

    def undock_tab(self, label: str) -> None:
        """Undock one canvas tab into floating window and track redock callback."""

        if label not in self.canvas_map or label in self.floating_windows:
            return
        index = CanvasTabManager._stack_index_for_label(self, label)
        if index < 0:
            return
        canvas_widget = self.canvas_map[label]
        wrapper = self.wrapper_map[label]
        remaining_labels = [
            route_key
            for route_key in getattr(self.pivot, "items", {})
            if route_key != label and route_key in self.pivot.items
        ]
        if self.pivot.currentRouteKey() == label and remaining_labels:
            next_label = remaining_labels[0]
            self.pivot.setCurrentItem(next_label)
            next_index = CanvasTabManager._stack_index_for_label(self, next_label)
            if next_index >= 0:
                self.stack.setCurrentIndex(next_index)
        self.pivot.removeWidget(label)
        self.stack.removeWidget(wrapper)
        self.update_tab_visibility()

        def redock(widget: QWidget, redock_label: str) -> None:
            """Restore one floating canvas page into the docked tab host."""

            insert_index = CanvasTabManager.insertion_index_for_label(
                self,
                redock_label,
            )
            pivot_item = CanvasTabManager._pivot_item_for(self, redock_label)
            self.pivot.insertWidget(insert_index, redock_label, pivot_item)
            self.canvas_map[redock_label] = widget
            redock_wrapper = QWidget()
            layout = QVBoxLayout(redock_wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.addWidget(widget)
            self.wrapper_map[redock_label] = redock_wrapper
            self.stack.insertWidget(insert_index, redock_wrapper)
            self.floating_windows.pop(redock_label, None)
            CanvasTabManager._set_canvas_detached(self, redock_label, False)
            canvas_availability = getattr(self, "_canvas_availability", {})
            fallback_labels = getattr(self, "_fallback_labels", {})
            if not canvas_availability.get(redock_label, True):
                CanvasAvailabilityPresenter.hide_pivot_item(
                    self,
                    redock_label,
                    fallback_label=fallback_labels.get(redock_label),
                )
            self.update_tab_visibility()
            if canvas_availability.get(redock_label, True):
                CanvasTabManager._activate_docked_canvas(self, redock_label)
                emit = getattr(getattr(self, "canvas_activated", None), "emit", None)
                if callable(emit):
                    emit(redock_label)
            self.visibility_changed.emit(True)
            CanvasTabManager._emit_layout_state_changed(self)

        canvas_widget.setParent(None)
        top_level_window = self.window()
        floating_chrome_factories = getattr(self, "_floating_chrome_factories", {})
        chrome_factory = floating_chrome_factories.get(
            label,
            _no_floating_chrome,
        )
        floating_chrome = chrome_factory()
        floating_window = CanvasTabManager._create_floating_window(
            self,
            canvas_widget,
            label,
            redock,
            backdrop_mode=getattr(top_level_window, "_backdrop_mode", None),
            floating_chrome=floating_chrome,
        )
        floating_window.setAttribute(Qt.WA_DeleteOnClose)  # type: ignore[attr-defined]
        floating_window.setWindowFlag(Qt.Window, True)  # type: ignore[attr-defined]
        floating_window.setWindowFlag(Qt.Tool, False)  # type: ignore[attr-defined]
        floating_window.setWindowModality(Qt.NonModal)  # type: ignore[attr-defined]
        page_title = getattr(self, "_canvas_titles", {}).get(label, label)
        if isinstance(floating_window, QObject):
            set_localized_window_title(
                floating_window,
                "%1 Canvas",
                page_title,
            )
        else:
            floating_window.setWindowTitle(
                render_application_text(app_text("%1 Canvas", page_title))
            )
        floating_window.setWindowIcon(self.window().windowIcon())
        layout_changed = getattr(floating_window, "layoutStateChanged", None)
        connect = getattr(layout_changed, "connect", None)
        if callable(connect):
            connect(lambda: CanvasTabManager._emit_layout_state_changed(self))
        self.floating_windows[label] = floating_window
        CanvasTabManager._set_canvas_detached(self, label, True)
        floating_window.resize(800, 600)
        floating_window.show()
        emit = getattr(getattr(self, "canvas_activated", None), "emit", None)
        if callable(emit):
            emit(label)
        if self.all_tabs_empty():
            self.visibility_changed.emit(False)
        CanvasTabManager._emit_layout_state_changed(self)

    def _create_floating_window(
        self,
        canvas_widget: QWidget,
        label: str,
        redock: Callable[[QWidget, str], None],
        *,
        backdrop_mode: ShellBackdropMode | None,
        floating_chrome: FloatingCanvasChrome | None,
    ) -> FloatingCanvasWindow:
        """Create a floating window, omitting chrome kwargs for simple test doubles."""

        if floating_chrome is None:
            return FloatingCanvasWindow(
                canvas_widget,
                label,
                redock,
                backdrop_mode=backdrop_mode,
            )
        return FloatingCanvasWindow(
            canvas_widget,
            label,
            redock,
            backdrop_mode=backdrop_mode,
            floating_chrome=floating_chrome,
        )

    def insertion_index_for_label(self, label: str) -> int:
        """Return the stable docked insertion index for one canvas label."""

        labels = list(self.canvas_map)
        if label not in labels:
            labels.append(label)
        ordered_available = [
            key
            for key in labels
            if (
                key == label
                or CanvasTabManager._stack_index_for_label(self, key) >= 0
                or key in self.pivot.items
            )
        ]
        return max(0, ordered_available.index(label))

    def rebuild_tab_indices(self) -> None:
        """Retain the legacy hook; stack indices are resolved live."""

        return

    def _stack_index_for_label(self, label: str) -> int:
        """Return the current stack index for a docked canvas wrapper."""

        wrapper = getattr(self, "wrapper_map", {}).get(label)
        index_of = getattr(self.stack, "indexOf", None)
        if wrapper is not None and callable(index_of):
            return int(index_of(wrapper))
        legacy_indices = getattr(self, "tab_indices", {})
        if isinstance(legacy_indices, dict):
            return int(legacy_indices.get(label, -1))
        return -1

    def _activate_docked_canvas(self, label: str) -> bool:
        """Select the docked stack page that currently owns the label."""

        if label not in getattr(self.pivot, "items", {}):
            return False
        stack_index = CanvasTabManager._stack_index_for_label(self, label)
        if stack_index < 0:
            return False
        self.stack.setCurrentIndex(stack_index)
        self.pivot.setCurrentItem(label)
        return True

    def update_tab_visibility(self) -> None:
        """Show the canvas selector only when multiple canvases are docked."""

        self.pivot.setVisible(len(self.pivot.items) > 1)

    def all_tabs_empty(self) -> bool:
        """Return True when no tabs remain docked in pivot strip."""

        return len(self.pivot.items) == 0

    def closeEvent(self, event: Any) -> None:
        """Close any floating windows before tab manager is destroyed."""

        self.closing = True
        for floating_window in list(self.floating_windows.values()):
            floating_window.close()
        event.accept()

    def _close_all_floating_windows(self) -> None:
        """Close all tracked floating windows on top-level window destruction."""

        for floating_window in list(self.floating_windows.values()):
            floating_window.close()

    def _pivot_mouse_press_event(self, event: Any) -> object:
        """Undock tab on pivot right-click while preserving left-click selection."""

        if event.button() == Qt.RightButton:  # type: ignore[attr-defined]
            for route_key, item in self.pivot.items.items():
                if item.geometry().contains(event.pos()):
                    self.undock_tab(route_key)
                    break
        return Pivot.mousePressEvent(self.pivot, event)

    def _install_pivot_undock_handler(self) -> None:
        """Route pivot mouse presses through the manager-owned undock handler."""

        self.pivot.mousePressEvent = self._pivot_mouse_press_event

    def _emit_layout_state_changed(self) -> None:
        """Emit the durable canvas layout signal when available."""

        emit = getattr(getattr(self, "layout_state_changed", None), "emit", None)
        if callable(emit):
            emit()

    def _create_pivot_item(self, label: str) -> DockablePivotItem:
        """Create a styled dockable pivot item for one canvas label."""

        title = getattr(self, "_canvas_titles", {}).get(label, label)
        pivot_item = DockablePivotItem("", self.pivot)
        apply_application_text(pivot_item, title)
        pivot_item.doubleClicked.connect(lambda: self.undock_tab(label))
        pivot_item.setStyleSheet(self._pivot_item_stylesheet())
        setFont(pivot_item, 14)
        pivot_item.adjustSize()
        return pivot_item

    def _connect_canvas_dock_action(self, label: str, widget: QWidget) -> None:
        """Connect one canvas dock-action signal to manager-owned behavior."""

        signal = getattr(widget, "dockActionRequested", None)
        connect = getattr(signal, "connect", None)
        if not callable(connect):
            return

        callbacks = getattr(self, "_canvas_dock_action_callbacks", None)
        if not isinstance(callbacks, dict):
            callbacks = {}
            self._canvas_dock_action_callbacks = callbacks

        previous_callback = callbacks.get(label)
        disconnect = getattr(signal, "disconnect", None)
        if previous_callback is not None and callable(disconnect):
            try:
                disconnect(previous_callback)
            except RuntimeError:
                pass

        def callback(*_args: object, route_label: str = label) -> None:
            """Route one canvas widget dock action back to the host manager."""

            self.handle_canvas_dock_action(route_label)

        callbacks[label] = callback
        connect(callback)

    def _set_canvas_detached(self, label: str, detached: bool) -> None:
        """Update one canvas widget's locale-neutral attachment state."""

        canvas = self.canvas_map.get(label)
        set_canvas_detached = getattr(canvas, "set_canvas_detached", None)
        if callable(set_canvas_detached):
            set_canvas_detached(detached)

    def _apply_theme_styles(self) -> None:
        """Reapply pivot item colors after theme or accent changes."""

        stylesheet = self._pivot_item_stylesheet()
        for item in self.pivot.items.values():
            item.setStyleSheet(stylesheet)

    def _pivot_item_stylesheet(self) -> str:
        """Return the pivot item stylesheet for the active theme."""

        if isDarkTheme():
            return """
            QPushButton[isSelected="false"] {
                color: #aaa;
            }
            QPushButton[isSelected="false"]:hover {
                color: #fff;
            }
            QPushButton[isSelected="true"] {
                color: #fff;
            }
            """
        return """
            QPushButton[isSelected="false"] {
                color: #60656b;
            }
            QPushButton[isSelected="false"]:hover {
                color: #1d2329;
            }
            QPushButton[isSelected="true"] {
                color: #11161b;
            }
            """

    @staticmethod
    def _pivot_item_for(view: object, label: str) -> DockablePivotItem:
        """Return a pivot item using test doubles when supplied."""

        create_pivot_item = getattr(view, "_create_pivot_item", None)
        if callable(create_pivot_item):
            return cast(DockablePivotItem, create_pivot_item(label))
        return CanvasTabManager._create_pivot_item(cast(CanvasTabManager, view), label)


def create_canvas_host(
    *,
    pages: Sequence[CanvasHostPage],
    parent: QWidget | None = None,
) -> CanvasTabManager:
    """Build a generic canvas-tab manager for already-created canvas pages."""

    return CanvasTabManager(parent=parent, pages=pages)


def _no_floating_chrome() -> FloatingCanvasChrome | None:
    """Return no floating chrome for generic canvas pages."""

    return None


__all__ = [
    "CanvasHostPage",
    "CanvasTabManager",
    "DockablePivotItem",
    "create_canvas_host",
]
