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

"""Verify field-state persistence for native Comfy values."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.panel.field_state_controller import (
    EditorPanelFieldStateController,
)
from substitute.presentation.editor.panel.widgets.fields.native import (
    ColorField,
    ColorsField,
)
from tests.support.qt.lifecycle import destroy_qt_object


def _ensure_qapp() -> QApplication:
    """Return the shared QApplication required by the native color field."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def test_native_semantic_value_signal_persists_through_field_state_owner() -> None:
    """Persist native values through the same cube-state owner as scalar fields."""

    _ensure_qapp()
    field = ColorField("#000000")
    field.setProperty(
        "input_metadata",
        {
            "cube_alias": "A",
            "node_name": "node",
            "key": "color",
            "type": "COLOR",
        },
    )
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"color": "#000000"}}}},
        dirty=False,
        field_control_states={},
    )
    controller = EditorPanelFieldStateController()
    try:
        controller.bind_node_widget_state(
            field,
            cube_state,
            {"node_name": "node", "key": "color"},
        )
        field.valueChanged.emit("#abcdef")

        assert cube_state.buffer["nodes"]["node"]["inputs"]["color"] == "#abcdef"
        assert cube_state.dirty is True
    finally:
        destroy_qt_object(field)


def test_native_palette_value_persists_as_an_ordered_graph_list() -> None:
    """Persist a COLORS value without flattening its ordered semantic shape."""

    _ensure_qapp()
    field = ColorsField(["#000000"])
    field.setProperty(
        "input_metadata",
        {
            "cube_alias": "A",
            "node_name": "node",
            "key": "color_palette",
            "type": "COLORS",
        },
    )
    cube_state = SimpleNamespace(
        buffer={"nodes": {"node": {"inputs": {"color_palette": ["#000000"]}}}},
        dirty=False,
        field_control_states={},
    )
    controller = EditorPanelFieldStateController()
    try:
        controller.bind_node_widget_state(
            field,
            cube_state,
            {"node_name": "node", "key": "color_palette"},
        )
        field.valueChanged.emit(["#abcdef", "#ffffff"])

        assert cube_state.buffer["nodes"]["node"]["inputs"]["color_palette"] == [
            "#abcdef",
            "#ffffff",
        ]
        assert cube_state.dirty is True
    finally:
        destroy_qt_object(field)
