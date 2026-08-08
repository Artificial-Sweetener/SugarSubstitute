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

"""Own node-card body ordering, separators, and row registration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.node_behavior import FieldBehavior
from substitute.presentation.editor.panel.node_card.body_contribution import (
    NodeCardBodyContribution,
)
from substitute.presentation.editor.panel.widgets.field_row import (
    BuiltFieldRow,
    FieldRowBuilder,
)
from substitute.presentation.editor.panel.widgets.node_card import (
    reconcile_node_card_body_separators,
)


class NodeCardBodyComposer:
    """Own node-card body ordering, separators, and visibility registration."""

    def __init__(self, *, panel: Any, field_rows: FieldRowBuilder) -> None:
        """Store collaborators used to build rows and separators."""

        self._panel = panel
        self._field_rows = field_rows

    def add_input_row(
        self,
        *,
        label: str,
        widget: QWidget,
        field_behavior: FieldBehavior,
        content_layout: QVBoxLayout,
    ) -> BuiltFieldRow:
        """Build and append one single-field row."""

        built_row = self._field_rows.build_input_row(
            label=label,
            widget=widget,
            field_behavior=field_behavior,
        )
        self._append_row(content_layout, built_row)
        return built_row

    def add_n_column_row(
        self,
        *,
        fields: list[tuple[str, QWidget]],
        field_behaviors: Mapping[str, FieldBehavior],
        content_layout: QVBoxLayout,
        node_name: str = "",
        field_labels: Mapping[str, str] | None = None,
        contribution: NodeCardBodyContribution | None = None,
    ) -> BuiltFieldRow:
        """Build, optionally decorate, and append one grouped field row."""

        built_row = self._field_rows.build_n_column_row(
            fields=fields,
            field_behaviors=field_behaviors,
            node_name=node_name,
            field_labels=field_labels,
        )
        if contribution is not None:
            contribution.row_decorator.decorate(built_row)
        self._append_row(content_layout, built_row)
        return built_row

    def reconcile_separator_visibility(self) -> None:
        """Show separators only between adjacent visible body rows."""

        row_widgets = getattr(self._panel, "row_widgets", {})
        if isinstance(row_widgets, Mapping):
            reconcile_node_card_body_separators(row_widgets)

    def _append_row(
        self,
        content_layout: QVBoxLayout,
        built_row: BuiltFieldRow,
    ) -> None:
        """Append a row and insert a separator only between body rows."""

        separator = self._create_separator(content_layout, built_row.field_key)
        content_layout.addWidget(built_row.row)
        self._register_row_widgets(built_row, separator)

    def _create_separator(
        self,
        content_layout: QVBoxLayout,
        field_key: str | None,
    ) -> QWidget | None:
        """Create a hidden separator before a row when another row exists."""

        if content_layout.count() == 0:
            return None
        parent = content_layout.parentWidget() or self._panel
        separator = self._field_rows.make_horizontal_divider(parent)
        if field_key is not None:
            separator.setProperty("divider_for_field", field_key)
        separator.setVisible(False)
        content_layout.addWidget(separator)
        return separator

    def _register_row_widgets(
        self,
        built_row: BuiltFieldRow,
        separator: QWidget | None,
    ) -> None:
        """Register normal rows with the hidden-field controller."""

        if built_row.field_key is None or not hasattr(self._panel, "row_widgets"):
            return
        self._panel.row_widgets[built_row.field_key] = (separator, built_row.row)


__all__ = ["NodeCardBodyComposer"]
