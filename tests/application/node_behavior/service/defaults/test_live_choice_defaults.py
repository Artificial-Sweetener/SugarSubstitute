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

"""Live choice-default resolution contracts."""

from __future__ import annotations


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldLabelSource,
    FieldValueSource,
)
from tests.support.node_behavior import (
    DummyNodeDefinitionGateway,
    cube_state,
)


def test_loaded_cube_missing_numeric_input_uses_live_default() -> None:
    """Loaded cubes should render missing numeric values from live defaults."""

    cube = cube_state(
        nodes={"sampler": {"class_type": "Sampler", "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "Sampler": {
                    "input": {
                        "required": {
                            "steps": ["INT", {"default": 20, "min": 1, "max": 150}]
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["sampler"]["steps"]
    assert spec.value == 20
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT
    assert spec.label_source is FieldLabelSource.COMFY_DEFINITION


def test_loaded_cube_missing_combo_uses_live_default() -> None:
    """Loaded cubes should render missing choices from live defaults."""

    cube = cube_state(
        nodes={"sampler": {"class_type": "Sampler", "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "Sampler": {
                    "input": {
                        "required": {
                            "sampler_name": [
                                ["euler", "ddim"],
                                {"default": "ddim"},
                            ],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["sampler"]["sampler_name"]
    assert spec.value == "ddim"
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT


def test_loaded_cube_missing_combo_without_default_uses_first_live_option() -> None:
    """Loaded cubes should render missing choices from the first live option."""

    cube = cube_state(
        nodes={"sampler": {"class_type": "Sampler", "inputs": {}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "Sampler": {
                    "input": {
                        "required": {
                            "sampler_name": [["euler", "ddim"], {}],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["sampler"]["sampler_name"]
    assert spec.value == "euler"
    assert spec.value_source == FieldValueSource.FIRST_OPTION


def test_loaded_cube_blank_combo_uses_live_default_without_dirtying() -> None:
    """Loaded cube blank choice literals should render live defaults without mutation."""

    cube = cube_state(
        nodes={"loader": {"class_type": "ModelLoader", "inputs": {"model": ""}}},
        ui={"canonical_cube": {"cube_id": "demo.cube"}},
    )
    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "ModelLoader": {
                    "input": {
                        "required": {
                            "model": [
                                ["authored.safetensors", "live-default.safetensors"],
                                {"default": "live-default.safetensors"},
                            ],
                        }
                    }
                }
            }
        )
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["loader"]["model"]
    assert spec.value == "live-default.safetensors"
    assert spec.value_source == FieldValueSource.LIVE_DEFAULT
    assert cube.buffer["nodes"]["loader"]["inputs"]["model"] == ""
    assert cube.dirty is False
