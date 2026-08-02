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

"""Render the docked canvas choice as an anchored combobox-style selector."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import SegmentedItem  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
)

from substitute.presentation.canvas.shared.canvas_nav_picker import (
    CanvasNavPicker,
    CanvasNavPickerItem,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_OVERLAY_INSET,
    CANVAS_CHROME_SURFACE_PADDING,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.canvas.host.canvas_host_state import (
    CanvasHostEntry,
    CanvasHostState,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
)

_MINIMUM_CONTROL_WIDTH = 72
_HORIZONTAL_TEXT_PADDING = 28


class CanvasHostSelector(QWidget):
    """Show the active canvas and open the shared anchored row picker."""

    def __init__(
        self,
        parent: QWidget,
        *,
        selected_callback: Callable[[str], None],
    ) -> None:
        """Create a content-sized selector overlay for one canvas host."""

        super().__init__(parent)
        self.setObjectName("CanvasHostSelector")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._selected_callback = selected_callback
        self._state: CanvasHostState | None = None

        self.surface = QLabel(self)
        self.surface.setObjectName("CanvasHostSelectorSurface")
        self.surface.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.surface.lower()

        self.button = SegmentedItem("", self)
        self.button.setObjectName("CanvasHostSelectorButton")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFixedHeight(CANVAS_CHROME_CONTROL_HEIGHT)
        self.button.clicked.connect(self._show_picker)
        self._picker = CanvasNavPicker(parent)

        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.hide()

    def present(self, state: CanvasHostState) -> None:
        """Project the authoritative canvas state into the selector overlay."""

        self._state = state
        items = state.selectable_entries()
        active_route_key = state.active_route_key
        active_item = next(
            (item for item in items if item.route_key == active_route_key),
            items[0] if items else None,
        )
        if active_item is not None:
            apply_application_text(self.button, active_item.page.title)
        control_width = self._control_width(items)
        self.button.setFixedSize(control_width, CANVAS_CHROME_CONTROL_HEIGHT)
        surface_width = control_width + (2 * CANVAS_CHROME_SURFACE_PADDING)
        surface_height = CANVAS_CHROME_CONTROL_HEIGHT + (
            2 * CANVAS_CHROME_SURFACE_PADDING
        )
        self.setFixedSize(surface_width, surface_height)
        self.surface.setGeometry(self.rect())
        self.button.move(
            CANVAS_CHROME_SURFACE_PADDING,
            CANVAS_CHROME_SURFACE_PADDING,
        )
        self.move(CANVAS_CHROME_OVERLAY_INSET, CANVAS_CHROME_OVERLAY_INSET)
        self.setVisible(len(items) > 1)
        if not self.isHidden():
            self.raise_()
        else:
            self._picker.close()

    def picker_visible(self) -> bool:
        """Return whether the selector popup is open for interaction tests."""

        return self._picker.is_visible()

    def changeEvent(self, event: QEvent) -> None:
        """Remeasure localized selector titles when the application language changes."""

        super().changeEvent(event)
        if event.type() == QEvent.Type.LanguageChange:
            state = self._state
            if state is not None:
                self.present(state)

    def _show_picker(self) -> None:
        """Open the shared canvas navigation picker for current host entries."""

        state = self._state
        if state is None:
            return
        entries = state.selectable_entries()
        if len(entries) <= 1:
            return
        picker_items = tuple(
            CanvasNavPickerItem(
                item.route_key,
                render_application_text(item.page.title),
            )
            for item in entries
        )
        self._picker.show_for(
            self.button,
            items=picker_items,
            active_key=state.active_route_key or "",
            row_width=self._control_width(entries),
            selected_callback=self._selected_callback,
        )

    def _control_width(self, items: tuple[CanvasHostEntry, ...]) -> int:
        """Measure one stable control width that fits every localized title."""

        label_width = max(
            (
                self.button.fontMetrics().horizontalAdvance(
                    render_application_text(item.page.title)
                )
                for item in items
            ),
            default=0,
        )
        return max(_MINIMUM_CONTROL_WIDTH, label_width + _HORIZONTAL_TEXT_PADDING)

    def _apply_theme_style(self) -> None:
        """Apply the shared floating navigation surface for the active theme."""

        self.surface.setStyleSheet(
            floating_canvas_surface_stylesheet("QLabel#CanvasHostSelectorSurface")
        )


__all__ = ["CanvasHostSelector"]
