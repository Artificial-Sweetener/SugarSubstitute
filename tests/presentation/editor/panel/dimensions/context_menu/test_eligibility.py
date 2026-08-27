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

"""Test dimension-row context-menu eligibility boundaries."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.domain.node_behavior import FieldBehavior
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder
from tests.presentation.editor.panel.dimensions.context_menu.support import (
    DimensionPanel,
    cleanup_widgets,
    first_row,
    spinbox,
)


def test_non_dimension_group_keeps_default_context_menu(
    qt_application_owner: QApplication,
) -> None:
    """Reject fields whose width and height stems do not form one pair."""

    panel = DimensionPanel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = spinbox(panel, value=512, key="source_width")
        height = spinbox(panel, value=768, key="target_height")
        builder = _builder(panel)

        builder.add_n_column_row(
            fields=[("source_width", width), ("target_height", height)],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "target_height": FieldBehavior(field_key="target_height"),
            },
            content_layout=content_layout,
            node_name="resize",
        )
        row = first_row(content_layout)

        assert row.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
        assert row.property("dimension_field_group") is None
    finally:
        cleanup_widgets(qt_application_owner, content, panel)


def test_unsupported_widgets_keep_default_context_menu(
    qt_application_owner: QApplication,
) -> None:
    """Reject a dimension pair without readable and writable value surfaces."""

    panel = DimensionPanel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        builder = _builder(panel)

        builder.add_n_column_row(
            fields=[
                ("source_width", QWidget(panel)),
                ("source_height", QWidget(panel)),
            ],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "source_height": FieldBehavior(field_key="source_height"),
            },
            content_layout=content_layout,
            node_name="resize",
        )
        row = first_row(content_layout)

        assert row.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
        assert row.property("dimension_field_group") is None
    finally:
        cleanup_widgets(qt_application_owner, content, panel)


def _builder(panel: DimensionPanel) -> FieldRowBuilder:
    """Build the production row owner around one test panel."""

    return FieldRowBuilder(
        panel=panel,
        icon_builder=lambda _icon: QWidget(panel),
        icon_resolver=lambda _node, _label, column_index=None: None,
    )
