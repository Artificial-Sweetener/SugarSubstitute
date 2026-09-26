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

"""Realize one scalar or full-width editor field row."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.display_labels import beautify_label
from substitute.application.node_behavior import FieldBehavior, LabelMode, RowMode
from substitute.presentation.editor.panel.field_visibility_policy import (
    field_key_is_hidden,
)
from substitute.presentation.qt_label_text import literal_label_text
from substitute.presentation.widgets.tooltips import (
    bind_fluent_tooltip,
    tooltip_from_input_metadata,
)

from .field_action_projection import field_action_contributions
from .field_row_geometry import (
    EDITOR_FULL_WIDTH_ROW_MARGINS,
    EDITOR_ROW_HORIZONTAL_MARGINS,
    EDITOR_ROW_ICON_SIZE,
    EDITOR_ROW_SPACING,
    ScalarFieldRowWidget,
    apply_editor_control_height,
    field_alignment_for_field,
    field_stretch_for_field,
    label_stretch_for_field,
    should_apply_editor_control_height,
    surface_may_size_field,
)
from .field_row_metadata import leaf_field_key, scoped_field_key
from .field_row_models import BuiltFieldRow, FieldRowTextTarget


def build_scalar_field_row(
    *,
    parent: QWidget,
    label: str,
    widget: QWidget,
    field_behavior: FieldBehavior,
    hidden_keys: frozenset[object],
) -> BuiltFieldRow:
    """Build one scalar or full-width field row from prepared behavior."""

    input_metadata = widget.property("input_metadata")
    field_tooltip = tooltip_from_input_metadata(input_metadata)
    field_key = scoped_field_key(input_metadata)
    leaf_key = leaf_field_key(input_metadata)
    action_contributions = field_action_contributions(((leaf_key or label, widget),))
    if field_behavior.row_mode == RowMode.FULL_WIDTH:
        padded = QWidget(parent)
        padded_layout = QVBoxLayout(padded)
        padded_layout.setContentsMargins(*EDITOR_FULL_WIDTH_ROW_MARGINS)
        padded_layout.setSpacing(6)
        padded_layout.addWidget(widget)
        if input_metadata is not None:
            padded.setProperty("input_metadata", input_metadata)
        padded.setVisible(not field_key_is_hidden(field_key, hidden_keys))
        bind_fluent_tooltip(
            padded,
            field_tooltip,
            padded,
            widget,
            show_delay_ms=600,
        )
        return BuiltFieldRow(
            field_key=field_key,
            row=padded,
            text_targets=(
                FieldRowTextTarget(
                    field_key=leaf_key,
                    label=None,
                    field_widget=widget,
                    tooltip_owner=padded,
                    tooltip_targets=(padded, widget),
                ),
            )
            if leaf_key is not None
            else (),
            action_contributions=action_contributions,
        )

    row = ScalarFieldRowWidget(parent)
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(*EDITOR_ROW_HORIZONTAL_MARGINS)
    row_layout.setSpacing(EDITOR_ROW_SPACING)
    row_layout.addSpacing(EDITOR_ROW_ICON_SIZE)
    label_widget: CaptionLabel | None = None
    if field_behavior.label_mode != LabelMode.HIDDEN:
        label_text = field_behavior.label_override or label
        label_widget = CaptionLabel(literal_label_text(beautify_label(label_text)))
        if field_behavior.label_mode == LabelMode.PROMPT:
            label_widget.setStyleSheet("font-weight: bold;")
        label_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        row_layout.addWidget(
            label_widget,
            label_stretch_for_field(widget),
            Qt.AlignmentFlag.AlignVCenter,
        )
    if surface_may_size_field(field_behavior):
        if should_apply_editor_control_height(field_behavior):
            apply_editor_control_height(widget)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
    row_layout.addWidget(
        widget,
        field_stretch_for_field(widget),
        field_alignment_for_field(widget),
    )
    row_layout.addSpacing(EDITOR_ROW_ICON_SIZE)
    if input_metadata is not None:
        row.setProperty("input_metadata", input_metadata)
    row.setVisible(not field_key_is_hidden(field_key, hidden_keys))
    tooltip_targets = (
        (row, widget) if label_widget is None else (row, label_widget, widget)
    )
    bind_fluent_tooltip(
        row,
        field_tooltip,
        *tooltip_targets,
        show_delay_ms=600,
    )
    return BuiltFieldRow(
        field_key=field_key,
        row=row,
        text_targets=(
            FieldRowTextTarget(
                field_key=leaf_key,
                label=label_widget,
                field_widget=widget,
                tooltip_owner=row,
                tooltip_targets=tooltip_targets,
            ),
        )
        if leaf_key is not None
        else (),
        action_contributions=action_contributions,
    )
