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

"""Wrapper choice-field contracts."""

from __future__ import annotations


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldValueSource,
)
from substitute.application.node_behavior.list_value_resolver import (
    extract_live_list_options,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)
from tests.application.node_behavior.service.support import (
    RequiredOnlyNodeDefinitionGateway,
)


def test_build_snapshot_enriches_wrapper_choices_from_live_body_definition() -> None:
    """Wrapper fields should expose live body COMBO options when public metadata is compact."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    cube = cube_state(
        nodes={
            "resize_by_factor": {
                "class_type": wrapper_id,
                "inputs": {"scheduler": "normal"},
            }
        },
        definitions={
            "SimpleSyrup.KSamplerExtras": {
                "input": {
                    "required": {
                        "scheduler": [
                            "LIST",
                            {"dynamic": True},
                        ],
                    }
                }
            }
        },
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Resize by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "id": "scheduler-interface",
                        "name": "scheduler",
                        "label": "Scheduler",
                        "type": "COMBO",
                        "linkIds": [1169],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {
                        "id": 1169,
                        "origin_id": -10,
                        "target_id": 1661,
                        "target_slot": 0,
                        "type": "COMBO",
                    }
                ],
                "nodes": [
                    {
                        "id": 1661,
                        "type": "SimpleSyrup.KSamplerExtras",
                        "inputs": [
                            {
                                "link": 1169,
                                "localized_name": "scheduler",
                                "name": "scheduler",
                                "type": "COMBO",
                                "widget": {"name": "scheduler"},
                            }
                        ],
                        "widgets_values": ["normal"],
                    }
                ],
            }
        ],
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "SimpleSyrup.KSamplerExtras": {
                "input": {
                    "required": {
                        "scheduler": [
                            ["normal", "karras"],
                            {"default": "normal"},
                        ],
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["resize_by_factor"]["scheduler"]

    assert spec.field_type == "LIST"
    assert extract_live_list_options(spec.field_info) == ("normal", "karras")
    assert spec.meta_info["options_resolved"] is True
    assert spec.meta_info["options_unavailable_reason"] is None
    assert spec.value == "normal"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_renders_wrapper_combo_without_default_or_input() -> None:
    """Wrapper COMBO fields with live options should render without stored values."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    service = NodeBehaviorService(
        node_definition_gateway=RequiredOnlyNodeDefinitionGateway(
            {
                "UpscaleModelLoader": {
                    "input": {
                        "required": {
                            "model_name": [
                                "COMBO",
                                {
                                    "options": [
                                        "ESRGAN_4x.pth",
                                        "R-ESRGAN 4x+ Anime6B.pth",
                                    ]
                                },
                            ]
                        }
                    },
                }
            }
        )
    )
    cube = cube_state(
        nodes={
            "resize_by_factor": {
                "class_type": wrapper_id,
                "inputs": {},
            }
        },
        definitions={},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Resize by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "id": "model-name-interface",
                        "name": "model_name",
                        "label": "Model",
                        "type": "COMBO",
                        "linkIds": [1169],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {
                        "id": 1169,
                        "origin_id": -10,
                        "target_id": 1661,
                        "target_slot": 0,
                        "type": "COMBO",
                    }
                ],
                "nodes": [
                    {
                        "id": 1661,
                        "type": "UpscaleModelLoader",
                        "inputs": [
                            {
                                "link": 1169,
                                "localized_name": "model_name",
                                "name": "model_name",
                                "type": "COMBO",
                                "widget": {"name": "model_name"},
                            }
                        ],
                        "widgets_values": [],
                    }
                ],
            }
        ],
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["resize_by_factor"]["model_name"]
    assert spec.field_type == "COMBO"
    assert extract_live_list_options(spec.field_info) == (
        "ESRGAN_4x.pth",
        "R-ESRGAN 4x+ Anime6B.pth",
    )
    assert spec.value == "ESRGAN_4x.pth"
    assert spec.value_source == FieldValueSource.FIRST_OPTION


def test_build_snapshot_preserves_wrapper_combo_widget_default() -> None:
    """Wrapper body widget values should remain defaults after live COMBO enrichment."""

    wrapper_id = "de2c84e5-02a8-4c50-831d-3c169dee4820"
    service = NodeBehaviorService(
        node_definition_gateway=RequiredOnlyNodeDefinitionGateway(
            {
                "UpscaleModelLoader": {
                    "input": {
                        "required": {
                            "model_name": [
                                "COMBO",
                                {
                                    "options": [
                                        "ESRGAN_4x.pth",
                                        "R-ESRGAN 4x+ Anime6B.pth",
                                    ]
                                },
                            ]
                        }
                    },
                }
            }
        )
    )
    cube = cube_state(
        nodes={
            "resize_by_factor": {
                "class_type": wrapper_id,
                "inputs": {},
            }
        },
        definitions={},
        subgraphs=[
            {
                "id": wrapper_id,
                "name": "Resize by Factor",
                "inputNode": {"id": -10},
                "inputs": [
                    {
                        "id": "model-name-interface",
                        "name": "model_name",
                        "label": "Model",
                        "type": "COMBO",
                        "linkIds": [1169],
                    },
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [
                    {
                        "id": 1169,
                        "origin_id": -10,
                        "target_id": 1661,
                        "target_slot": 0,
                        "type": "COMBO",
                    }
                ],
                "nodes": [
                    {
                        "id": 1661,
                        "type": "UpscaleModelLoader",
                        "inputs": [
                            {
                                "link": 1169,
                                "localized_name": "model_name",
                                "name": "model_name",
                                "type": "COMBO",
                                "widget": {"name": "model_name"},
                            }
                        ],
                        "widgets_values": ["R-ESRGAN 4x+ Anime6B.pth"],
                    }
                ],
            }
        ],
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["resize_by_factor"]["model_name"]
    assert spec.meta_info["default"] == "R-ESRGAN 4x+ Anime6B.pth"
    assert spec.value == "R-ESRGAN 4x+ Anime6B.pth"
    assert spec.value_source == FieldValueSource.AUTHORED_DEFAULT
