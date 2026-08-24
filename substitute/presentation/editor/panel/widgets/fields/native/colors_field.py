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

"""Provide a Fluent palette editor for native Comfy COLORS values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial
import re

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FlowLayout,
    FluentIcon,
    TransparentToolButton,
)

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import set_localized_tooltip
from substitute.presentation.dialogs import LocalizedColorPickerButton
from substitute.presentation.localization import LocalizedPushButton

_MAX_COLORS = 16
_NEUTRAL_COLOR = "#ffffff"
_RGB_HEX_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}\Z")


class ColorsField(QWidget):
    """Edit an ordered Comfy palette without changing its semantic list shape."""

    valueChanged = Signal(object)

    def __init__(
        self,
        value: object,
        parent: QWidget | None = None,
        *,
        maximum_colors: int = _MAX_COLORS,
    ) -> None:
        """Initialize a palette with explicit add, remove, and ordering controls."""

        super().__init__(parent)
        if not 1 <= maximum_colors <= _MAX_COLORS:
            raise ValueError("maximum_colors must be between one and sixteen")
        self._maximum_colors = maximum_colors
        self._colors: list[str] = []
        self._selected_index: int | None = None
        self.pickers: list[LocalizedColorPickerButton] = []

        self._swatch_surface = QWidget(self)
        self._swatch_layout = FlowLayout(self._swatch_surface, needAni=False)
        self._swatch_layout.setContentsMargins(0, 0, 0, 0)
        self._swatch_layout.setHorizontalSpacing(6)
        self._swatch_layout.setVerticalSpacing(6)

        self.add_button = LocalizedPushButton(app_text("Add"), self)
        self.remove_button = LocalizedPushButton(app_text("Remove"), self)
        self.move_up_button = TransparentToolButton(FluentIcon.UP, self)
        self.move_down_button = TransparentToolButton(FluentIcon.DOWN, self)
        set_localized_tooltip(self.move_up_button, "Move up")
        set_localized_tooltip(self.move_down_button, "Move down")

        self.move_up_button.setFixedSize(28, 28)
        self.move_down_button.setFixedSize(28, 28)
        self.add_button.clicked.connect(self._add_color)
        self.remove_button.clicked.connect(self._remove_selected_color)
        self.move_up_button.clicked.connect(partial(self._move_selected_color, -1))
        self.move_down_button.clicked.connect(partial(self._move_selected_color, 1))

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        actions.addWidget(self.move_up_button)
        actions.addWidget(self.move_down_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._swatch_surface)
        layout.addLayout(actions)

        self.setValue(value)

    def value(self) -> list[str]:
        """Return a detached ordered palette for graph-state persistence."""

        return list(self._colors)

    def setValue(self, value: object) -> None:  # noqa: N802
        """Apply a palette without publishing an application state change."""

        self._colors = self._normalized_palette(value)[: self._maximum_colors]
        self._selected_index = 0 if self._colors else None
        self._rebuild_swatches()

    def _add_color(self) -> None:
        """Append Comfy's neutral white swatch within the native limit."""

        if len(self._colors) >= self._maximum_colors:
            return
        self._colors.append(_NEUTRAL_COLOR)
        self._selected_index = len(self._colors) - 1
        self._rebuild_swatches()
        self._publish_value()

    def _remove_selected_color(self) -> None:
        """Remove the selected swatch and retain a neighboring selection."""

        index = self._selected_index
        if index is None:
            return
        self._colors.pop(index)
        self._selected_index = min(index, len(self._colors) - 1)
        if not self._colors:
            self._selected_index = None
        self._rebuild_swatches()
        self._publish_value()

    def _move_selected_color(self, offset: int) -> None:
        """Move the selected swatch by one position when a neighbor exists."""

        index = self._selected_index
        if index is None:
            return
        destination = index + offset
        if destination < 0 or destination >= len(self._colors):
            return
        self._colors[index], self._colors[destination] = (
            self._colors[destination],
            self._colors[index],
        )
        self._selected_index = destination
        self._rebuild_swatches()
        self._publish_value()

    def _select_color(self, index: int) -> None:
        """Select one swatch before its modal color editor opens."""

        self._selected_index = index
        self._refresh_control_state()

    def _commit_picker_color(self, index: int, color: QColor) -> None:
        """Commit one accepted RGB color while preserving palette order."""

        if index >= len(self._colors):
            return
        self._colors[index] = color.name(QColor.NameFormat.HexRgb)
        self._selected_index = index
        self._refresh_control_state()
        self._publish_value()

    def _rebuild_swatches(self) -> None:
        """Recreate index-bound swatches after a structural palette edit."""

        self._swatch_layout.takeAllWidgets()
        self.pickers = []
        for index, color in enumerate(self._colors):
            picker = LocalizedColorPickerButton(
                QColor(color),
                app_text("Choose color"),
                self._swatch_surface,
            )
            picker.setFixedSize(36, 28)
            picker.setCheckable(True)
            picker.pressed.connect(partial(self._select_color, index))
            picker.colorChanged.connect(partial(self._commit_picker_color, index))
            self._swatch_layout.addWidget(picker)
            self.pickers.append(picker)
        self._refresh_control_state()

    def _refresh_control_state(self) -> None:
        """Reflect selection and native palette limits in action availability."""

        selected = self._selected_index
        self.add_button.setEnabled(len(self._colors) < self._maximum_colors)
        self.remove_button.setEnabled(selected is not None)
        self.move_up_button.setEnabled(selected is not None and selected > 0)
        self.move_down_button.setEnabled(
            selected is not None and selected < len(self._colors) - 1
        )
        for index, picker in enumerate(self.pickers):
            picker.setProperty("selected", index == selected)
            picker.setChecked(index == selected)

    def _publish_value(self) -> None:
        """Publish a detached palette through the shared semantic field contract."""

        self.valueChanged.emit(self.value())

    @staticmethod
    def _normalized_palette(value: object) -> list[str]:
        """Normalize supported Comfy palette containers and neutralize bad entries."""

        raw_colors: object
        if isinstance(value, Mapping):
            raw_colors = list(value.values())
        else:
            raw_colors = value
        if not isinstance(raw_colors, Sequence) or isinstance(
            raw_colors, (str, bytes, bytearray)
        ):
            return []

        normalized: list[str] = []
        for raw_color in raw_colors[:_MAX_COLORS]:
            if not isinstance(raw_color, str):
                normalized.append(_NEUTRAL_COLOR)
                continue
            color = (
                QColor(raw_color) if _RGB_HEX_PATTERN.fullmatch(raw_color) else QColor()
            )
            normalized.append(
                color.name(QColor.NameFormat.HexRgb)
                if color.isValid()
                else _NEUTRAL_COLOR
            )
        return normalized


__all__ = ["ColorsField"]
