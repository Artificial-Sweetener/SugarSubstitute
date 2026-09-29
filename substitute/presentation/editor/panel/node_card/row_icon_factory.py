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

"""Build the optional icon slot used by node-card field rows."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]
from qfluentwidgets import IconWidget

from substitute.presentation.editor.panel.widgets.field_row_geometry import (
    EDITOR_ROW_ICON_SIZE,
)


class NodeCardRowIconFactory:
    """Own node-card row icon resolution and fixed-slot construction."""

    def __init__(self, *, panel: Any) -> None:
        """Use the panel as the fallback parent for detached row construction."""

        self._panel = panel

    @staticmethod
    def resolve(
        node_name: str,
        row_label: str,
        column_index: int | None = None,
    ) -> FIF | None:
        """Return the optional icon assigned to one row slot."""

        _ = (node_name, row_label, column_index)
        return None

    def build(
        self,
        icon_enum: FIF | None,
        parent: QWidget | None = None,
    ) -> QWidget:
        """Return an icon widget or a fixed-size spacer for an empty slot."""

        widget_parent = parent if parent is not None else self._panel
        if icon_enum:
            icon = IconWidget(icon_enum, widget_parent)
            icon.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
            return cast(QWidget, icon)
        spacer = QWidget(widget_parent)
        spacer.setFixedSize(EDITOR_ROW_ICON_SIZE, EDITOR_ROW_ICON_SIZE)
        return spacer


__all__ = ["NodeCardRowIconFactory"]
