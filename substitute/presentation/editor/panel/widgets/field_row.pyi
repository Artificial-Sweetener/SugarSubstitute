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

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    DimensionRowActions,
)
from substitute.presentation.editor.field_actions import FieldActionContribution

EDITOR_ROW_HEIGHT: int
EDITOR_ROW_HORIZONTAL_MARGINS: tuple[int, int, int, int]
EDITOR_ROW_ICON_SIZE: int
EDITOR_ROW_SPACING: int
EDITOR_ROW_BODY_SPACING: int
EDITOR_FIELD_ROW_HEIGHT: int
EDITOR_FULL_WIDTH_ROW_MARGINS: tuple[int, int, int, int]
GROUPED_FIELD_DIVIDER_WIDTH: int

class BuiltFieldRow:
    field_key: Any
    row: QWidget
    text_targets: tuple[FieldRowTextTarget, ...]
    dimension_actions: DimensionRowActions | None
    action_contributions: tuple[FieldActionContribution, ...]
    def __init__(
        self,
        field_key: Any,
        row: QWidget,
        text_targets: tuple[FieldRowTextTarget, ...] = ...,
        dimension_actions: DimensionRowActions | None = ...,
        action_contributions: tuple[FieldActionContribution, ...] = ...,
    ) -> None: ...

class FieldRowTextTarget:
    field_key: str
    label: Any | None
    field_widget: QWidget
    tooltip_owner: QWidget
    tooltip_targets: tuple[QWidget, ...]

class ScalarFieldRowWidget(QWidget):
    def __init__(self, parent: QWidget | None = ...) -> None: ...

class FieldRowBuilder:
    def __init__(
        self,
        *,
        panel: Any,
        icon_builder: Any,
        icon_resolver: Any,
        dimension_preset_source: DimensionPresetCatalogSource | None = ...,
    ) -> None: ...
    def make_horizontal_divider(self, parent: QWidget) -> QWidget: ...
    def build_input_row(self, *args: Any, **kwargs: Any) -> BuiltFieldRow: ...
    def build_n_column_row(self, *args: Any, **kwargs: Any) -> BuiltFieldRow: ...
    def add_input_row(self, *args: Any, **kwargs: Any) -> Any: ...
    def add_n_column_row(self, *args: Any, **kwargs: Any) -> Any: ...
    def gather_visible_keys(
        self,
        *,
        input_keys: list[str],
        field_groups: tuple[tuple[str, ...], ...],
        skip_keys: set[str],
    ) -> list[list[str]]: ...

def apply_editor_row_height(widget: QWidget) -> None: ...
def apply_editor_control_height(widget: QWidget) -> None: ...
def make_grouped_field_divider(
    parent: QWidget,
    *,
    field_key: Any = ...,
) -> QWidget: ...
