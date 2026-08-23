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

"""Nested wrapper-input resolution contracts."""

from __future__ import annotations


import pytest

from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldValueSource,
    LiveNodeDefinitionError,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)
from tests.application.node_behavior.service.support import (
    UUID_NESTED_WRAPPER,
    UUID_WRAPPER,
    RequiredOnlyNodeDefinitionGateway,
    _nested_wrapper_definitions,
    _nested_wrapper_live_definitions,
    _nested_wrapper_subgraphs,
    _wrapper_definitions,
    _wrapper_live_definitions,
    _wrapper_nodes,
    _wrapper_subgraphs,
)


def test_wrapper_surface_missing_live_body_definition_raises() -> None:
    """Wrapper body metadata must come from live Comfy definitions."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )

    with pytest.raises(LiveNodeDefinitionError) as error_info:
        build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert error_info.value.operation == "resolve wrapper body node metadata"
    assert error_info.value.missing_definitions[0].class_type == "DetailerForEach"
    assert error_info.value.missing_definitions[0].cube_aliases == ("A",)
    assert error_info.value.missing_definitions[0].node_names == ("detailer",)


def test_wrapper_body_metadata_uses_required_definition_lookup() -> None:
    """Wrapper body metadata should synchronously require live Comfy definitions."""

    cube = cube_state(
        nodes=_wrapper_nodes(),
        definitions=_wrapper_definitions(),
        subgraphs=_wrapper_subgraphs(),
    )
    gateway = RequiredOnlyNodeDefinitionGateway(_wrapper_live_definitions())
    service = NodeBehaviorService(node_definition_gateway=gateway)

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.field_specs_by_alias["A"]["detailer"]["denoise"].field_type == (
        "FLOAT"
    )
    assert "DetailerForEach" in gateway.required_requests
    assert "DetailerForEach" not in gateway.optional_requests


def test_wrapper_nested_public_input_is_exposed_from_nested_wrapper_default() -> None:
    """Parent wrapper fields routed through nested wrappers should still render."""

    cube = cube_state(
        nodes={
            "detailer": {
                "class_type": UUID_WRAPPER,
                "inputs": {},
            },
        },
        definitions=_nested_wrapper_definitions(),
        subgraphs=_nested_wrapper_subgraphs(),
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=_nested_wrapper_live_definitions(),
    )

    detailer_specs = snapshot.field_specs_by_alias["A"]["detailer"]
    assert list(detailer_specs) == ["c"]
    scale_factor = detailer_specs["c"]
    assert scale_factor.field_type == "FLOAT"
    assert scale_factor.value == 1.5
    assert scale_factor.value_source == FieldValueSource.AUTHORED_DEFAULT
    assert scale_factor.constraints == {"min": 0.25, "max": 3.0, "step": 0.05}
    assert scale_factor.meta_info["label"] == "Scale Factor"
    assert scale_factor.meta_info["interface_type"] == "INT,FLOAT,IMAGE,LATENT"
    assert UUID_NESTED_WRAPPER not in snapshot.field_specs_by_alias["A"]
    assert "PrimitiveFloat" not in snapshot.field_specs_by_alias["A"]


def test_wrapper_public_constraints_override_body_primitive_constraints() -> None:
    """Wrapper fields should preserve authored public bounds over body primitive bounds."""

    cube = cube_state(
        nodes={
            "upscale_by_factor": {
                "class_type": UUID_WRAPPER,
                "inputs": {},
            },
        },
        definitions=_nested_wrapper_definitions(),
        subgraphs=_nested_wrapper_subgraphs(),
    )
    cube.buffer["definitions"] = {
        "PrimitiveFloat": {
            "input": {
                "required": {
                    "value": [
                        "FLOAT",
                        {
                            "default": 1.0,
                            "min": -9_223_372_036_854_775_807,
                            "max": 9_223_372_036_854_775_807,
                            "step": 0.1,
                        },
                    ]
                }
            }
        }
    }
    subgraphs = cube.buffer["subgraphs"]
    assert isinstance(subgraphs, list)
    wrapper = subgraphs[0]
    assert isinstance(wrapper, dict)
    inputs = wrapper["inputs"]
    assert isinstance(inputs, list)
    public_input = inputs[0]
    assert isinstance(public_input, dict)
    public_input["min"] = 0.1
    public_input["max"] = 10.0

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "PrimitiveFloat": {
                "input": {
                    "required": {
                        "value": [
                            "FLOAT",
                            {
                                "default": 1.0,
                                "min": -9_223_372_036_854_775_807,
                                "max": 9_223_372_036_854_775_807,
                                "step": 0.1,
                            },
                        ]
                    }
                }
            }
        },
    )

    scale_factor = snapshot.field_specs_by_alias["A"]["upscale_by_factor"]["c"]
    assert scale_factor.meta_info["label"] == "Scale Factor"
    assert scale_factor.constraints == {"min": 0.1, "max": 10.0, "step": 0.1}
