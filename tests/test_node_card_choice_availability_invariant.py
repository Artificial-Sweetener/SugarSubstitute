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

"""Enforce that authoritative Comfy choice fields always render node cards."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.widgets import ComboBox
from tests.node_behavior_test_helpers import build_behavior_snapshot
from tests.node_card_builder_test_helpers import build_node_card_builder


class _NodeDefinitionGateway:
    """Return deterministic live definitions for invariant rendering tests."""

    def __init__(self, definitions: Mapping[str, dict[str, object]]) -> None:
        """Store live definitions by Comfy node class."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one optional object-info payload."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one required object-info payload."""

        definition = self._definitions.get(node_class)
        return {node_class: definition} if definition is not None else {}


class _CubeState:
    """Carry the mutable cube state consumed by production node-card building."""

    def __init__(self, nodes: dict[str, object]) -> None:
        """Initialize one non-dirty cube with the supplied nodes."""

        self.buffer: dict[str, object] = {"nodes": nodes, "definitions": {}}
        self.ui: dict[str, object] = {}
        self.dirty = False


class _Panel(QWidget):
    """Expose the production panel registries needed by node-card construction."""

    def __init__(self, cube_state: _CubeState) -> None:
        """Initialize one panel containing a single cube."""

        super().__init__()
        self._stack_order = ["Cube"]
        self._cube_states = {"Cube": cube_state}
        self.row_widgets: dict[object, object] = {}
        self.input_widgets_by_field_key: dict[tuple[str, str, str], object] = {}

    @staticmethod
    def is_connection(value: object) -> bool:
        """Recognize the legacy two-item connection representation."""

        return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)


@pytest.mark.parametrize(
    ("section_name", "field_info"),
    (
        ("required", [[], {}]),
        ("required", ["COMBO", {"options": []}]),
        ("optional", [[], {}]),
        ("optional", ["COMBO", {"options": []}]),
    ),
    ids=(
        "required-classic-list",
        "required-combo-options",
        "optional-classic-list",
        "optional-combo-options",
    ),
)
def test_authoritative_empty_choice_always_draws_node_card(
    section_name: str,
    field_info: list[object],
) -> None:
    """An authoritative zero-option picker must render instead of raising."""

    application = QApplication.instance() or QApplication([])
    node_name = "upscale_model"
    node_class = "UpscaleModelLoader"
    definitions: dict[str, dict[str, object]] = {
        node_class: {
            "input": {
                section_name: {
                    "model_name": field_info,
                }
            }
        }
    }
    nodes: dict[str, object] = {
        node_name: {
            "class_type": node_class,
            "inputs": {"model_name": "missing-upscaler.pth"},
        }
    }
    cube_state = _CubeState(nodes)
    panel = _Panel(cube_state)
    gateway = _NodeDefinitionGateway(definitions)
    builder = build_node_card_builder(panel, gateway)
    snapshot = build_behavior_snapshot(
        cube_states={"Cube": cube_state},
        stack_order=["Cube"],
        definitions_by_class=definitions,
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=cast(
            dict[str, object], cast(dict[str, object], nodes[node_name])["inputs"]
        ),
        node_type=node_class,
        field_specs=snapshot.field_specs_by_alias["Cube"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["Cube"][node_name],
        display_decision=snapshot.card_decisions_by_alias["Cube"][node_name],
        alias="Cube",
    )

    assert wrapper is not None
    assert wrapper.property("base_card_visible") is True
    choice = panel.input_widgets_by_field_key[("Cube", node_name, "model_name")]
    assert isinstance(choice, ComboBox)
    assert choice.count() == 0
    assert choice.currentText() == ""
    assert choice.placeholderText() == "No options available"
    assert cube_state.dirty is False

    wrapper.deleteLater()
    panel.deleteLater()
    application.processEvents()
