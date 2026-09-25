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

"""Render single-field and grouped field rows for behavior-driven node cards."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.node_behavior import FieldBehavior, LabelMode
from substitute.presentation.editor.panel.dimension_presets import (
    DimensionPresetCatalogSource,
)
from substitute.presentation.editor.panel.field_grouping import (
    group_visible_field_keys,
)
from substitute.presentation.editor.panel.menus.dimension_row_actions import (
    bind_dimension_row_actions,
)
from substitute.presentation.widgets.tooltips import (
    bind_fluent_tooltip,
    tooltip_from_input_metadata,
)
from substitute.application.display_labels import beautify_label
from substitute.presentation.qt_label_text import literal_label_text
from .field_action_projection import field_action_contributions
from .field_row_geometry import (
    EDITOR_ROW_HORIZONTAL_MARGINS,
    EDITOR_ROW_ICON_SIZE,
    EDITOR_ROW_SPACING,
    ScalarFieldRowWidget,
    apply_editor_control_height,
    field_alignment_for_field,
    field_stretch_for_field,
    label_stretch_for_field,
    make_grouped_field_divider,
    make_horizontal_field_divider,
    should_apply_editor_control_height,
    surface_may_size_field,
)
from .field_row_models import BuiltFieldRow, FieldRowTextTarget
from .field_row_metadata import scoped_field_key
from .scalar_field_row_realizer import build_scalar_field_row


class FieldRowBuilder:
    """Build tagged field rows/dividers so panel-level visibility toggles remain stable."""

    def __init__(
        self,
        panel: Any,
        icon_builder: Callable[[Any], QWidget],
        icon_resolver: Callable[[str, str, int | None], Any],
        dimension_preset_source: DimensionPresetCatalogSource | None = None,
    ) -> None:
        """Store panel collaborators used to build stable field-row widgets."""

        self._panel = panel
        self._icon_builder = icon_builder
        self._icon_resolver = icon_resolver
        self._dimension_preset_source = dimension_preset_source

    def make_horizontal_divider(self, parent: QWidget) -> QWidget:
        """Create one horizontal divider row."""

        return make_horizontal_field_divider(parent)

    def add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
        content_layout: QVBoxLayout,
    ) -> None:
        """Render one input row and register row widgets for hidden-field toggles."""

        built_row = self.build_input_row(
            label=label,
            widget=widget,
            field_behavior=field_behavior,
        )
        content_layout.addWidget(built_row.row)
        if built_row.field_key is not None:
            self._panel.row_widgets[built_row.field_key] = (None, built_row.row)

    def build_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
    ) -> BuiltFieldRow:
        """Build one input row without assigning body-level separators."""

        return build_scalar_field_row(
            parent=self._panel,
            label=label,
            widget=widget,
            field_behavior=field_behavior,
            hidden_keys=frozenset(
                getattr(self._panel, "_hidden_field_keys", set[object]())
            ),
        )

    def add_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        content_layout: QVBoxLayout,
        node_name: str = "",
        field_labels: Mapping[str, str] | None = None,
    ) -> None:
        """Render a grouped n-column row with divider and visibility tracking."""

        built_row = self.build_n_column_row(
            fields=fields,
            field_behaviors=field_behaviors,
            node_name=node_name,
            field_labels=field_labels,
        )
        content_layout.addWidget(built_row.row)
        if built_row.field_key is not None:
            self._panel.row_widgets[built_row.field_key] = (None, built_row.row)

    def build_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        node_name: str = "",
        field_labels: Mapping[str, str] | None = None,
    ) -> BuiltFieldRow:
        """Build one grouped n-column row without body-level separators."""

        panel = self._panel
        if not hasattr(panel, "col_widgets"):
            panel.col_widgets = {}

        row_container = ScalarFieldRowWidget(panel)
        row_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        row_container.setStyleSheet("background-color: transparent;")

        row_layout = QHBoxLayout(row_container)
        row_layout.setContentsMargins(*EDITOR_ROW_HORIZONTAL_MARGINS)
        row_layout.setSpacing(EDITOR_ROW_SPACING)
        column_widgets: dict[str, QWidget] = {}
        column_tooltips: list[str] = []
        first_field_key = None
        text_targets: list[FieldRowTextTarget] = []

        for index, (label, widget) in enumerate(fields):
            behavior = field_behaviors.get(label)
            input_metadata = widget.property("input_metadata")
            field_tooltip = tooltip_from_input_metadata(input_metadata)
            if field_tooltip is not None:
                column_tooltips.append(field_tooltip)
            field_key = scoped_field_key(input_metadata)
            if first_field_key is None and field_key is not None:
                first_field_key = field_key

            col = ScalarFieldRowWidget(panel)
            column_widgets[label] = col
            col_layout = QHBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(EDITOR_ROW_SPACING)

            icon_enum = self._icon_resolver(node_name, label, index)
            if icon_enum is None:
                col_layout.addSpacing(EDITOR_ROW_ICON_SIZE)
            else:
                icon_widget = self._icon_builder(icon_enum)
                col_layout.addWidget(icon_widget, 0, Qt.AlignmentFlag.AlignVCenter)

            label_text = (
                behavior.label_override
                if behavior is not None and behavior.label_override
                else (field_labels or {}).get(label, label)
            )
            label_widget: CaptionLabel | None = None
            if behavior is None or behavior.label_mode != LabelMode.HIDDEN:
                label_widget = CaptionLabel(
                    literal_label_text(beautify_label(label_text))
                )
                label_widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred,
                )
                col_layout.addWidget(
                    label_widget,
                    label_stretch_for_field(widget),
                    Qt.AlignmentFlag.AlignVCenter,
                )
            if surface_may_size_field(behavior):
                if should_apply_editor_control_height(behavior):
                    apply_editor_control_height(widget)
                widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred,
                )
            col_layout.addWidget(
                widget,
                field_stretch_for_field(widget),
                field_alignment_for_field(widget),
            )
            tooltip_targets = (
                (col, widget) if label_widget is None else (col, label_widget, widget)
            )
            bind_fluent_tooltip(
                col,
                field_tooltip,
                *tooltip_targets,
                show_delay_ms=600,
            )
            text_targets.append(
                FieldRowTextTarget(
                    field_key=label,
                    label=label_widget,
                    field_widget=widget,
                    tooltip_owner=col,
                    tooltip_targets=tooltip_targets,
                )
            )

            if field_key is not None:
                col.setProperty("field_key", field_key)
                widget.setProperty("field_key", field_key)
                panel.col_widgets[field_key] = (row_container, col, widget)

            row_layout.addWidget(col, 1)

            if index < len(fields) - 1:
                divider = make_grouped_field_divider(
                    panel,
                    field_key=field_key,
                )
                row_layout.addWidget(divider, 0, Qt.AlignmentFlag.AlignVCenter)

        row_layout.addSpacing(EDITOR_ROW_ICON_SIZE)
        dimension_actions = bind_dimension_row_actions(
            row_container=row_container,
            fields=fields,
            column_widgets=column_widgets,
            dimension_preset_source=self._dimension_preset_source,
        )
        action_sources: list[tuple[str, object]] = []
        if dimension_actions is not None:
            action_sources.append(
                (
                    ".".join(key for key, _widget in fields),
                    dimension_actions,
                )
            )
        action_sources.extend(
            (
                key,
                widget,
            )
            for key, widget in fields
        )
        unique_tooltips = set(column_tooltips)
        bind_fluent_tooltip(
            row_container,
            column_tooltips[0] if len(unique_tooltips) == 1 else None,
            row_container,
            show_delay_ms=600,
        )
        return BuiltFieldRow(
            field_key=first_field_key,
            row=row_container,
            text_targets=tuple(text_targets),
            dimension_actions=dimension_actions,
            action_contributions=field_action_contributions(tuple(action_sources)),
        )

    def gather_visible_keys(
        self,
        *,
        input_keys: list[str],
        field_groups: tuple[tuple[str, ...], ...],
        skip_keys: set[str],
    ) -> list[list[str]]:
        """Group visible field keys using resolved behavior-provided grouping rules."""

        return group_visible_field_keys(
            input_keys=input_keys,
            field_groups=field_groups,
            skip_keys=skip_keys,
        )


__all__ = ["FieldRowBuilder"]
