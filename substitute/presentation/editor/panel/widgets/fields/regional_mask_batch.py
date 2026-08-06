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

"""Render ordered regional masks as a selectable expanding editor list."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QColor, QEnterEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import PushButton  # type: ignore[import-untyped]
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    translate_application_text,
)

from substitute.presentation.regional import region_color


class _RegionalMaskRow(QPushButton):
    """Publish row-local hover intent without owning regional association state."""

    hoverChanged = Signal(int, bool)

    def __init__(self, label: str, index: int, parent: QWidget) -> None:
        """Create one row with its immutable ordered position."""

        super().__init__(label, parent)
        self._region_index = index

    def enterEvent(self, event: QEnterEvent) -> None:
        """Publish transient entry into this ordered region row."""

        super().enterEvent(event)
        self.hoverChanged.emit(self._region_index, True)

    def leaveEvent(self, event: QEvent) -> None:
        """Publish transient exit from this ordered region row."""

        super().leaveEvent(event)
        self.hoverChanged.emit(self._region_index, False)


class RegionalMaskBatchEditor(QFrame):
    """Display one expanded selected mask and compact unselected mask rows."""

    regionActionRequested = Signal(str, str, str)
    regionHoverChanged = Signal(object)

    def __init__(
        self,
        *,
        cube_alias: str,
        node_name: str,
        values: list[str],
        parent: QWidget | None = None,
    ) -> None:
        """Build ordered rows from the current authored Comfy list value."""

        super().__init__(parent)
        self.cube_alias = cube_alias
        self.node_name = node_name
        self._values = list(values)
        self._selected_index = 0 if values else -1
        self._hovered_index: int | None = None
        self._rows: list[QPushButton] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._rows_host = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        self._layout.addWidget(self._rows_host)
        action_row = QWidget(self)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)
        self._add_button = PushButton(app_text("Add"), action_row)
        self._add_button.setProperty("region_add_button", True)
        self._add_button.clicked.connect(self._add_region)
        action_layout.addWidget(self._add_button)
        self._import_button = PushButton(app_text("Choose Mask"), action_row)
        self._import_button.setProperty("region_import_button", True)
        self._import_button.clicked.connect(self._import_regions)
        action_layout.addWidget(self._import_button)
        self._remove_button = PushButton(app_text("Remove"), action_row)
        self._remove_button.setProperty("region_remove_button", True)
        self._remove_button.clicked.connect(self._remove_selected_region)
        action_layout.addWidget(self._remove_button)
        self._layout.addWidget(action_row)
        self._rebuild_rows()

    @property
    def selected_index(self) -> int:
        """Return the currently expanded ordered mask index."""

        return self._selected_index

    @property
    def region_count(self) -> int:
        """Return the number of authored ordered regions shown by the widget."""

        return len(self._values)

    def select_region(self, index: int) -> None:
        """Expand one mask row and contract every other row."""

        if not 0 <= index < len(self._rows):
            return
        self._selected_index = index
        self._remove_button.setEnabled(bool(self._rows))
        for row_index, row in enumerate(self._rows):
            selected = row_index == index
            row.setMinimumHeight(48 if selected else 28)
            row.setProperty("region_selected", selected)
            row.style().unpolish(row)
            row.style().polish(row)

    def set_hovered_region(self, index: int | None) -> None:
        """Render linked hover without changing the expanded selection."""

        resolved_index = (
            index if index is not None and 0 <= index < len(self._rows) else None
        )
        if resolved_index == self._hovered_index:
            return
        self._hovered_index = resolved_index
        total = len(self._rows)
        for row_index, row in enumerate(self._rows):
            row.setStyleSheet(
                _row_style(
                    region_color(row_index, total),
                    hovered=row_index == resolved_index,
                )
            )

    def set_regions(self, values: list[str], *, selected_index: int | None) -> None:
        """Render an authoritative ordered collection snapshot from workflow state."""

        self._values = list(values)
        self._selected_index = (
            selected_index
            if selected_index is not None and 0 <= selected_index < len(values)
            else (0 if values else -1)
        )
        self._hovered_index = None
        self._rebuild_rows()

    def _add_region(self) -> None:
        """Request durable region materialization without inventing local state."""

        self.regionActionRequested.emit(
            self.cube_alias,
            self.node_name,
            "@region:add",
        )

    def _import_regions(self) -> None:
        """Choose arbitrary mask files and append one ordered region per file."""

        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            translate_application_text("Choose Mask"),
            "",
            translate_application_text("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        next_index = len(self._values)
        for offset, path in enumerate(paths):
            payload = json.dumps(
                [next_index + offset, path],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.regionActionRequested.emit(
                self.cube_alias,
                self.node_name,
                f"@region:import:{payload}",
            )

    def _remove_selected_region(self) -> None:
        """Publish exact removal intent and await authoritative collection state."""

        index = self._selected_index
        if not 0 <= index < len(self._values):
            return
        self.regionActionRequested.emit(
            self.cube_alias,
            self.node_name,
            f"@region:remove:{index}",
        )

    def _rebuild_rows(self) -> None:
        """Recreate compact rows with deterministic palette colors and labels."""

        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()
        total = len(self._values)
        for index, value in enumerate(self._values):
            row = _RegionalMaskRow(
                _row_label(value, index),
                index,
                self._rows_host,
            )
            row.setProperty("region_index", index)
            color = region_color(index, total)
            row.setStyleSheet(_row_style(color, hovered=False))
            row.hoverChanged.connect(self._handle_row_hover)
            row.clicked.connect(
                lambda _checked=False, selected=index: self._select_and_emit(selected)
            )
            self._rows.append(row)
            self._rows_layout.addWidget(row)
        if self._rows:
            self.select_region(min(self._selected_index, len(self._rows) - 1))
        else:
            self._remove_button.setEnabled(False)

    def _select_and_emit(self, index: int) -> None:
        """Request matching durable canvas and collection selection."""

        self.regionActionRequested.emit(
            self.cube_alias,
            self.node_name,
            f"@region:select:{index}",
        )

    def _handle_row_hover(self, index: int, hovered: bool) -> None:
        """Publish transient row hover and keep local linked styling in sync."""

        next_index = index if hovered else None
        self.set_hovered_region(next_index)
        self.regionHoverChanged.emit(next_index)


def _row_label(value: str, index: int) -> str:
    """Return a stable visible row label without owning authored region names."""

    stem = Path(value).stem.strip()
    return stem or f"#{index + 1}"


def _row_style(color: QColor, *, hovered: bool) -> str:
    """Return deterministic row styling for baseline and linked hover states."""

    background = "rgba(255, 255, 255, 24)" if hovered else "transparent"
    return (
        "QPushButton { text-align: left; padding: 4px 8px; "
        f"border-left: 4px solid {color.name()}; background-color: {background}; }}"
    )


__all__ = ["RegionalMaskBatchEditor"]
