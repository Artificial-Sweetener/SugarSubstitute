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

"""Test dimension-row binding and base menu composition."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.domain.node_behavior import FieldBehavior
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.editor.panel.widgets.field_row import FieldRowBuilder
from substitute.presentation.widgets.menu_model import MenuItem, MenuSubmenu
from tests.presentation.editor.panel.dimensions.context_menu.support import (
    DimensionPanel as _Panel,
    add_dimension_row as _add_dimension_row,
    cleanup_widgets as _cleanup_widgets,
    counting_spinbox as _counting_spinbox,
    ensure_worker_application as _ensure_app,
    first_row as _first_row,
    install_recording_dimension_menu,
    spinbox as _spinbox,
    submenu as _submenu,
)


def test_dimension_group_context_menu_swaps_width_and_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-clicking a dimension row should expose and run the swap action."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=512, key="source_width")
        height = _spinbox(panel, value=768, key="source_height")
        builder = FieldRowBuilder(
            panel=panel,
            icon_builder=lambda _icon: QWidget(panel),
            icon_resolver=lambda _node, _label, column_index=None: None,
        )

        builder.add_n_column_row(
            fields=[("source_width", width), ("source_height", height)],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "source_height": FieldBehavior(field_key="source_height"),
            },
            content_layout=content_layout,
            node_name="resize",
        )
        row = _first_row(content_layout)

        assert row.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        assert row.property("dimension_field_group") == [
            "source_width",
            "source_height",
        ]

        row.customContextMenuRequested.emit(QPoint(4, 4))

        menu = menu_recording.root
        assert [action.text() for action in menu.actions] == ["Swap width & height"]
        menu.actions[0].trigger()

        assert width.value() == 768
        assert height.value() == 512
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_binding_does_not_read_values_during_row_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card construction should not read width or height until an action needs values."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _counting_spinbox(panel, value=512, key="source_width")
        height = _counting_spinbox(panel, value=768, key="source_height")

        _add_dimension_row(panel, content_layout, width=width, height=height)

        assert width.value_reads == 0
        assert height.value_reads == 0

        width.customContextMenuRequested.emit(QPoint(1, 1))
        assert width.value_reads == 0
        assert height.value_reads == 0

        menu_recording.root.actions[0].trigger()
        assert width.value_reads == 1
        assert height.value_reads == 1
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_without_saved_source_omits_set_dimensions_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saved dimensions should be absent unless a source is provided."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        width.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = menu_recording.root
        assert [submenu.title for submenu in root_menu.submenus] == [
            "Set ratio by Width"
        ]
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_group_context_menu_contains_aspect_ratio_submenus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dimension row context menu should expose the decided ratio preset lists."""

    app = _ensure_app()
    menu_recording = install_recording_dimension_menu(monkeypatch)
    panel = _Panel()
    content = QWidget(panel)
    try:
        content_layout = QVBoxLayout(content)
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        _add_dimension_row(panel, content_layout, width=width, height=height)

        width.customContextMenuRequested.emit(QPoint(1, 1))

        root_menu = menu_recording.root
        assert [action.text() for action in root_menu.actions] == [
            "Swap width & height"
        ]
        aspect_menu = _submenu(root_menu, "Set ratio by Width")
        landscape_menu = _submenu(aspect_menu, "Landscape")
        portrait_menu = _submenu(aspect_menu, "Portrait")
        assert [action.text() for action in landscape_menu.actions] == [
            "1:1",
            "5:4",
            "4:3",
            "3:2",
            "16:9",
            "2:1",
            "21:9",
        ]
        assert [action.text() for action in portrait_menu.actions] == [
            "1:1",
            "4:5",
            "3:4",
            "2:3",
            "9:16",
            "1:2",
            "9:21",
        ]
    finally:
        _cleanup_widgets(app, content, panel)


def test_dimension_row_contributes_side_complete_node_actions() -> None:
    """A dimension row should expose both ratio anchors to a node-level menu."""

    app = _ensure_app()
    panel = _Panel()
    content = QWidget(panel)
    try:
        width = _spinbox(panel, value=1600, key="source_width")
        height = _spinbox(panel, value=900, key="source_height")
        built_row = FieldRowBuilder(
            panel=panel,
            icon_builder=lambda _icon: QWidget(panel),
            icon_resolver=lambda _node, _label, column_index=None: None,
        ).build_n_column_row(
            fields=[("source_width", width), ("source_height", height)],
            field_behaviors={
                "source_width": FieldBehavior(field_key="source_width"),
                "source_height": FieldBehavior(field_key="source_height"),
            },
            field_labels={
                "source_width": "Source width",
                "source_height": "Source height",
            },
            node_name="resize",
        )

        assert len(built_row.action_contributions) == 1
        contribution = built_row.action_contributions[0]
        assert contribution.is_available() is True
        entries = contribution.entries(FieldActionContext(QPoint()))
        assert isinstance(entries[0], MenuItem)
        assert entries[0].label == "Swap width & height"
        assert [entry.label for entry in entries if isinstance(entry, MenuSubmenu)] == [
            "Set ratio by Width",
            "Set ratio by Height",
        ]

        assert entries[0].callback is not None
        entries[0].callback()
        assert width.value() == 900
        assert height.value() == 1600
    finally:
        _cleanup_widgets(app, content, panel)
