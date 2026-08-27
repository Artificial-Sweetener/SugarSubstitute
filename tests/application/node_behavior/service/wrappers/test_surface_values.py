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

"""Wrapper-surface value contracts."""

from __future__ import annotations


from substitute.application.node_behavior import (
    EnabledSwitchPolicy,
    FieldValueSource,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)
from tests.application.node_behavior.service.support import (
    UUID_WRAPPER,
    _wrapper_definitions,
    _wrapper_live_definitions,
    _wrapper_subgraphs,
)


def test_wrapper_surface_node_gets_title_control_when_all_inputs_are_linked() -> None:
    """Wrapper nodes should render public default controls from interface links."""

    cube = cube_state(
        nodes={
            "source": {"class_type": "ImageSource", "inputs": {"path": "a.png"}},
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {"image": ["source", 0]},
            },
        },
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    detailer_specs = snapshot.field_specs_by_alias["A"]["detailer"]
    detailer_decision = snapshot.card_decisions_by_alias["A"]["detailer"]
    detailer_behavior = snapshot.resolved_nodes_by_alias["A"]["detailer"]
    assert list(detailer_specs) == ["image", "steps", "cfg", "sampler_name", "denoise"]
    assert detailer_specs["steps"].value == 12
    assert detailer_specs["steps"].raw_value is None
    assert detailer_specs["steps"].value_source == FieldValueSource.AUTHORED_DEFAULT
    assert detailer_specs["cfg"].value == 7.0
    assert detailer_specs["sampler_name"].value == "euler_ancestral"
    assert detailer_specs["denoise"].value == 0.65
    assert detailer_specs["denoise"].constraints["min"] == 0.0001
    assert detailer_decision.visible is True
    assert detailer_decision.show_enabled_switch is False
    assert detailer_behavior.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert detailer_behavior.card.icon_name == "application"


def test_wrapper_surface_value_overrides_linked_body_default() -> None:
    """Surface wrapper inputs should override extracted hidden body widget defaults."""

    cube = cube_state(
        nodes={
            "source": {"class_type": "ImageSource", "inputs": {"path": "a.png"}},
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {"image": ["source", 0], "denoise": 0.8},
            },
        },
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    denoise = snapshot.field_specs_by_alias["A"]["detailer"]["denoise"]
    assert denoise.value == 0.8
    assert denoise.raw_value == 0.8
    assert denoise.value_source == FieldValueSource.EXPLICIT
