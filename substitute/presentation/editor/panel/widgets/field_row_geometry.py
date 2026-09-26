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

"""Own editor field-row sizing, alignment, divider, and theme geometry."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    StyleSheetBase,
    getStyleSheet,
    setCustomStyleSheet,
    setStyleSheet,
    styleSheetManager,
)

from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    RowMode,
)
from substitute.presentation.shell.chrome_style import field_row_divider_rgba_for_theme

_WIDE_ROW_FIELD_WIDGET_CLASSES = frozenset({"ModelPickerField"})
EDITOR_ROW_HEIGHT = 33
EDITOR_ROW_HORIZONTAL_MARGINS = (10, 0, 10, 0)
EDITOR_ROW_ICON_SIZE = 20
EDITOR_ROW_SPACING = 6
EDITOR_ROW_BODY_SPACING = 8
EDITOR_FIELD_ROW_HEIGHT = EDITOR_ROW_HEIGHT + (EDITOR_ROW_BODY_SPACING * 2)
EDITOR_FULL_WIDTH_ROW_MARGINS = (
    EDITOR_ROW_HORIZONTAL_MARGINS[0],
    EDITOR_ROW_BODY_SPACING,
    EDITOR_ROW_HORIZONTAL_MARGINS[2],
    EDITOR_ROW_BODY_SPACING,
)
GROUPED_FIELD_DIVIDER_WIDTH = 1


class ScalarFieldRowWidget(QWidget):
    """Render one editor scalar row with a stable visual height contribution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize a row container constrained to the scalar row height."""

        super().__init__(parent)
        apply_editor_row_height(self)

    def sizeHint(self) -> QSize:
        """Return the natural row width with the standard field-row height."""

        hint = super().sizeHint()
        return QSize(hint.width(), EDITOR_FIELD_ROW_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Return the natural minimum width with the standard field-row height."""

        hint = super().minimumSizeHint()
        return QSize(hint.width(), EDITOR_FIELD_ROW_HEIGHT)


def apply_editor_row_height(widget: QWidget) -> None:
    """Constrain one editor row container to the standard visual row height."""

    widget.setFixedHeight(EDITOR_FIELD_ROW_HEIGHT)


def apply_editor_control_height(widget: QWidget) -> None:
    """Constrain one scalar editor control to the standard fixed row height."""

    widget.setFixedHeight(EDITOR_ROW_HEIGHT)


def make_grouped_field_divider(
    parent: QWidget,
    *,
    field_key: Any = None,
) -> QWidget:
    """Create one standard themed divider for adjacent grouped-row items."""

    divider = QWidget(parent)
    divider.setFixedSize(GROUPED_FIELD_DIVIDER_WIDTH, EDITOR_ROW_HEIGHT)
    divider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    _apply_field_row_divider_style(divider)
    if field_key is not None:
        divider.setProperty("vertical_divider_for_field", field_key)
    return divider


class _FieldRowDividerStyleSheet(StyleSheetBase):  # type: ignore[misc]
    """Provide an empty QFluent-managed base source for custom divider QSS."""

    def path(self, theme: object | None = None) -> str:
        """Return no path because divider QSS is stored as custom QSS."""

        del theme
        return ""

    def content(self, theme: object | None = None) -> str:
        """Return no base content so only custom theme QSS paints dividers."""

        del theme
        return ""


_FIELD_ROW_DIVIDER_STYLE_SHEET = _FieldRowDividerStyleSheet()


def make_horizontal_field_divider(parent: QWidget) -> QWidget:
    """Create one standard themed horizontal divider."""

    line = QWidget(parent)
    line.setFixedHeight(1)
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    _apply_field_row_divider_style(line)
    return line


def surface_may_size_field(field_behavior: FieldBehavior | None) -> bool:
    """Return whether row policy may override a control's owned geometry."""

    return not (
        field_behavior is not None
        and field_behavior.presentation is FieldPresentation.SEED_BOX
    )


def should_apply_editor_control_height(field_behavior: FieldBehavior | None) -> bool:
    """Return whether one field widget should fill the scalar row height."""

    if field_behavior is not None and (
        field_behavior.presentation == FieldPresentation.PROMPT_BOX
        or field_behavior.row_mode == RowMode.FULL_WIDTH
    ):
        return False
    return True


def label_stretch_for_field(widget: QWidget) -> int:
    """Return the label stretch factor for the row containing this field."""

    return 0 if _field_should_own_surplus_width(widget) else 1


def field_stretch_for_field(widget: QWidget) -> int:
    """Return the field stretch factor for the row containing this field."""

    return 1 if _field_should_own_surplus_width(widget) else 0


def field_alignment_for_field(widget: QWidget) -> Qt.AlignmentFlag:
    """Return row alignment for one field widget."""

    del widget
    return Qt.AlignmentFlag.AlignVCenter


def _field_should_own_surplus_width(widget: QWidget) -> bool:
    """Return whether a value widget should receive flexible row width."""

    return _is_wide_row_field(widget) or _is_fill_width_string_input(widget)


def _is_wide_row_field(widget: QWidget) -> bool:
    """Return whether a field widget should own surplus row width."""

    return any(
        candidate.__name__ in _WIDE_ROW_FIELD_WIDGET_CLASSES
        for candidate in widget.__class__.mro()
    )


def _is_fill_width_string_input(widget: QWidget) -> bool:
    """Return whether one scalar field is a single-line string input."""

    input_metadata = widget.property("input_metadata")
    return (
        widget.__class__.__name__ == "LineEdit"
        and isinstance(input_metadata, Mapping)
        and input_metadata.get("type") == "STRING"
    )


def _apply_field_row_divider_style(widget: QWidget) -> None:
    """Register one field-row divider with QFluent theme refresh."""

    light_qss = _field_row_divider_qss(field_row_divider_rgba_for_theme(False))
    dark_qss = _field_row_divider_qss(field_row_divider_rgba_for_theme(True))
    setStyleSheet(widget, _FIELD_ROW_DIVIDER_STYLE_SHEET)
    setCustomStyleSheet(widget, light_qss, dark_qss)
    widget.setStyleSheet(getStyleSheet(styleSheetManager.source(widget)))


def _field_row_divider_qss(rgba: str) -> str:
    """Return divider QSS that changes only paint color, not layout metrics."""

    return f"background-color: {rgba}; margin: 0px; padding: 0px;"
