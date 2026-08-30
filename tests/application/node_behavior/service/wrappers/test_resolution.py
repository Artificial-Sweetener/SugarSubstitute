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

"""Wrapper-definition resolution contracts."""

from __future__ import annotations


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldLabelSource,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)
from tests.application.node_behavior.service.support import (
    UUID_WRAPPER,
    RecordingNodeDefinitionGateway,
    _wrapper_definitions,
    _wrapper_live_definitions,
    _wrapper_nodes,
    _wrapper_subgraphs,
)


def test_behavior_snapshot_uses_subgraph_wrapper_virtual_definition() -> None:
    """Wrapper nodes should resolve fields from public subgraph interfaces."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    detailer_specs = snapshot.field_specs_by_alias["A"]["detailer"]
    assert list(detailer_specs) == ["image", "steps", "cfg", "sampler_name", "denoise"]
    assert detailer_specs["image"].field_type == "IMAGE"
    assert detailer_specs["steps"].field_type == "INT"
    assert detailer_specs["cfg"].field_type == "FLOAT"
    assert detailer_specs["sampler_name"].field_type == "LIST"
    assert detailer_specs["denoise"].field_type == "FLOAT"
    assert detailer_specs["denoise"].constraints == {
        "min": 0.0001,
        "max": 1.0,
        "step": 0.01,
    }
    assert "tooltip" not in detailer_specs["denoise"].meta_info
    assert detailer_specs["steps"].meta_info["subgraph_wrapper"] is True
    assert detailer_specs["steps"].meta_info["subgraph_id"] == UUID_WRAPPER
    assert detailer_specs["steps"].label_source is FieldLabelSource.WRAPPER_AUTHORED


def test_behavior_snapshot_does_not_project_subgraph_body_nodes() -> None:
    """Subgraph body nodes should not enter behavior maps or field specs."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    assert list(snapshot.resolved_nodes_by_alias["A"]) == ["source", "detailer"]
    assert "DetailerForEach" not in snapshot.resolved_nodes_by_alias["A"]
    assert "DetailerForEach" not in snapshot.field_specs_by_alias["A"]


def test_behavior_snapshot_does_not_query_live_gateway_for_uuid_wrapper() -> None:
    """UUID wrappers should resolve locally instead of querying live Comfy metadata."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )
    gateway = RecordingNodeDefinitionGateway(_wrapper_live_definitions())
    service = NodeBehaviorService(node_definition_gateway=gateway)

    service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert UUID_WRAPPER not in gateway.requests
    assert "ImageSource" in gateway.requests


def test_wrapper_display_name_is_available_for_card_behavior() -> None:
    """Resolved wrapper behavior should expose the public subgraph display name."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_wrapper_live_definitions(),
    )

    assert snapshot.resolved_nodes_by_alias["A"]["detailer"].display_name == "Detailer"
