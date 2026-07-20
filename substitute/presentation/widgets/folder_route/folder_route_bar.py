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

"""Render QFluent folder route controls for picker surfaces."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import translate_application_text

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BreadcrumbBar,
    SingleDirectionScrollArea,
    TransparentPushButton,
)

from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)

from .folder_route_tree import FolderRouteChild, FolderRouteTree

_ROOT_ROUTE_KEY = "root"
_CHILD_SCROLL_HEIGHT = 42
_HORIZONTAL_SCROLL_BAR_HEIGHT = 6
_HORIZONTAL_SCROLL_BAR_BOTTOM_MARGIN = 1


class FolderRouteBar(QWidget):
    """Render a breadcrumb and horizontally scrollable child route strip."""

    routeChanged = Signal(tuple)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the breadcrumb row and child route strip."""

        super().__init__(parent)
        self._route_tree = FolderRouteTree(())
        self._current_route: tuple[str, ...] = ()
        self._route_by_key: dict[str, tuple[str, ...]] = {}
        self._suppress_route_signal = False

        self._breadcrumb = BreadcrumbBar(self)
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_changed)

        self._child_scroll = SingleDirectionScrollArea(
            self,
            orient=Qt.Orientation.Horizontal,
        )
        configure_qfluent_scroll_surface(self._child_scroll)
        self._child_scroll.setObjectName("folderRouteChildScroll")
        self._child_scroll.setWidgetResizable(True)
        self._child_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._child_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._child_scroll.enableTransparentBackground()
        self._child_scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {"
            "border: none;"
            "background: transparent;"
            "}"
        )
        self._child_scroll.setFixedHeight(_CHILD_SCROLL_HEIGHT)
        self._make_horizontal_scroll_bar_thin()

        self._child_content = QWidget(self._child_scroll)
        self._child_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._child_layout = QHBoxLayout(self._child_content)
        self._child_layout.setContentsMargins(0, 0, 0, _HORIZONTAL_SCROLL_BAR_HEIGHT)
        self._child_layout.setSpacing(6)
        self._child_layout.addStretch(1)
        self._child_scroll.setWidget(self._child_content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._breadcrumb)
        layout.addWidget(self._child_scroll)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._rebuild()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Retranslate the application-owned root breadcrumb in place."""

        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            self._rebuild()

    def set_route_tree(self, route_tree: FolderRouteTree) -> None:
        """Replace the route tree and refresh route controls."""

        self._route_tree = route_tree
        if not self._route_tree.item_ids_under(self._current_route):
            self._current_route = ()
        self._rebuild()

    def set_current_route(self, route: tuple[str, ...]) -> None:
        """Select one route without emitting when the route is unchanged."""

        if route == self._current_route:
            return
        self._current_route = route
        self._rebuild()

    def current_route(self) -> tuple[str, ...]:
        """Return the currently selected route."""

        return self._current_route

    def child_route_buttons(self) -> tuple[TransparentPushButton, ...]:
        """Return visible child route buttons in display order."""

        buttons: list[TransparentPushButton] = []
        for index in range(self._child_layout.count()):
            item = self._child_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if isinstance(widget, TransparentPushButton):
                buttons.append(widget)
        return tuple(buttons)

    def sizeHint(self) -> QSize:
        """Return a height based on the currently visible route rows."""

        hint = super().sizeHint()
        return QSize(hint.width(), hint.height())

    def _make_horizontal_scroll_bar_thin(self) -> None:
        """Constrain QFluent's route-strip scrollbar to a slim horizontal rail.

        QFluent's smooth scrollbar hardcodes a 12 px horizontal geometry. The
        route strip needs the same QFluent scrolling behavior with a lighter
        affordance, so this instance-level adapter preserves the widget while
        overriding only its route-local sizing and handle placement.
        """

        scroll_bar = self._child_scroll.hScrollBar

        def adjust_pos(size: QSize) -> None:
            scroll_bar.resize(
                max(0, size.width() - 2),
                _HORIZONTAL_SCROLL_BAR_HEIGHT,
            )
            scroll_bar.move(
                1,
                max(
                    0,
                    size.height()
                    - _HORIZONTAL_SCROLL_BAR_HEIGHT
                    - _HORIZONTAL_SCROLL_BAR_BOTTOM_MARGIN,
                ),
            )

        def adjust_handle_pos() -> None:
            total = max(scroll_bar.maximum() - scroll_bar.minimum(), 1)
            delta = int(scroll_bar.value() / total * scroll_bar._slideLength())
            y = max(0, (scroll_bar.height() - scroll_bar.handle.height()) // 2)
            scroll_bar.handle.move(scroll_bar._padding + delta, y)

        scroll_bar._adjustPos = adjust_pos
        scroll_bar._adjustHandlePos = adjust_handle_pos
        adjust_pos(self._child_scroll.size())

    def _rebuild(self) -> None:
        """Rebuild breadcrumb and child route controls for the current route."""

        self._suppress_route_signal = True
        self._rebuild_breadcrumb()
        self._rebuild_child_routes()
        self._suppress_route_signal = False

    def _rebuild_breadcrumb(self) -> None:
        """Rebuild the breadcrumb row from the current route."""

        self._breadcrumb.clear()
        self._route_by_key = {_ROOT_ROUTE_KEY: ()}
        self._breadcrumb.addItem(_ROOT_ROUTE_KEY, translate_application_text("All"))
        for index, label in enumerate(self._current_route):
            route = self._current_route[: index + 1]
            route_key = self._route_key(route)
            self._route_by_key[route_key] = route
            self._breadcrumb.addItem(route_key, label)
        self._breadcrumb.setCurrentItem(self._route_key(self._current_route))
        self._breadcrumb.setVisible(bool(self._current_route))

    def _rebuild_child_routes(self) -> None:
        """Rebuild the horizontally scrollable child route row."""

        self._clear_child_route_buttons()
        children = self._route_tree.children(self._current_route)
        insert_index = max(0, self._child_layout.count() - 1)
        for child in children:
            button = self._child_route_button(child)
            self._child_layout.insertWidget(insert_index, button)
            insert_index += 1
        self._child_content.adjustSize()
        self._child_scroll.setVisible(bool(children))
        self.setVisible(bool(self._current_route) or bool(children))
        self.updateGeometry()

    def _clear_child_route_buttons(self) -> None:
        """Remove existing child route buttons while preserving layout stretch."""

        for button in self.child_route_buttons():
            self._child_layout.removeWidget(button)
            button.deleteLater()

    def _child_route_button(self, child: FolderRouteChild) -> TransparentPushButton:
        """Create one child route button."""

        button = TransparentPushButton(f"{child.label} ({child.item_count})", self)
        button.setCheckable(False)
        button.setProperty("folderRoute", child.route)
        button.clicked.connect(
            lambda checked=False, route=child.route: self._emit_route(route)
        )
        return button

    def _on_breadcrumb_changed(self, route_key: str) -> None:
        """Translate QFluent breadcrumb route keys back to tuple routes."""

        if self._suppress_route_signal:
            return
        route = self._route_by_key.get(route_key)
        if route is None:
            return
        self._emit_route(route)

    def _emit_route(self, route: tuple[str, ...]) -> None:
        """Update current route and emit when a new route is selected."""

        if route == self._current_route:
            return
        self._current_route = route
        self._rebuild()
        self.routeChanged.emit(route)

    def _route_key(self, route: tuple[str, ...]) -> str:
        """Return the current rebuild's key for a route."""

        if not route:
            return _ROOT_ROUTE_KEY
        return f"route:{len(route)}:{'/'.join(route)}"


__all__ = ["FolderRouteBar"]
