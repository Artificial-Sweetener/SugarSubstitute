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

"""Model-field icon enrichment contracts."""

from __future__ import annotations


from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.node_behavior import (
    FieldBehaviorPatch,
    FieldPresentation,
    NodeBehaviorPatch,
    PackageBehaviorPatch,
)
from tests.support.node_behavior import (
    DummyNodeDefinitionGateway,
    build_behavior_snapshot,
    cube_state,
)
from tests.application.node_behavior.service.support import (
    _model_detector,
    _model_item,
)


def test_build_snapshot_adds_model_icon_for_non_rich_model_host() -> None:
    """Model-backed ordinary COMBO hosts should receive the default model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
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
        ),
        model_backed_node_detector=_model_detector(
            _model_item("upscale_models", "R-ESRGAN 4x+ Anime6B.pth"),
            kinds=("upscale_models",),
        ),
    )
    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
            }
        },
        definitions={
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
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    behavior = snapshot.resolved_nodes_by_alias["A"]["load_upscale_model"]
    spec = snapshot.field_specs_by_alias["A"]["load_upscale_model"]["model_name"]
    assert behavior.card.icon_name == "model"
    assert spec.field_behavior.presentation == FieldPresentation.STANDARD


def test_build_snapshot_uses_host_model_icon_for_checkpoint_loader() -> None:
    """Checkpoint graphical picker hosts should receive the built-in model icon."""

    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "Anime\\preview.safetensors"},
            }
        },
        definitions={
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            [
                                "Anime\\preview.safetensors",
                                "Realism\\base.safetensors",
                            ],
                            {},
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["checkpoint"].card.icon_name == "model"


def test_build_snapshot_uses_host_model_icon_for_vae_loader() -> None:
    """VAE graphical picker hosts should receive the built-in model icon."""

    cube = cube_state(
        nodes={
            "vae": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ClearVAE.safetensors"},
            }
        },
        definitions={
            "VAELoader": {
                "input": {
                    "required": {
                        "vae_name": [["ClearVAE.safetensors", "OtherVAE.pt"], {}]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["vae"].card.icon_name == "model"


def test_build_snapshot_adds_model_icon_for_explicit_model_picker_field() -> None:
    """Explicit graphical model picker fields should receive the default model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {"required": {"ckpt_name": ["STRING", {}]}},
                }
            }
        )
    )
    cube = cube_state(
        nodes={
            "checkpoint": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {},
            }
        },
        definitions={
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": ["STRING", {}]}},
            }
        },
    )
    runtime_state = service.ensure_runtime_state(cube)
    runtime_state.node_instance_patch = PackageBehaviorPatch(
        by_node_instance={
            "A:checkpoint": NodeBehaviorPatch(
                field_patches={
                    "ckpt_name": FieldBehaviorPatch(
                        presentation=FieldPresentation.MODEL_PICKER,
                        style={"model_kind": "checkpoints"},
                    )
                }
            )
        }
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    behavior = snapshot.resolved_nodes_by_alias["A"]["checkpoint"]
    spec = snapshot.field_specs_by_alias["A"]["checkpoint"]["ckpt_name"]
    assert behavior.card.icon_name == "model"
    assert spec.field_behavior.presentation == FieldPresentation.MODEL_PICKER


def test_build_snapshot_preserves_explicit_icon_for_model_backed_node() -> None:
    """Explicit host icons should win over the default model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(),
        model_backed_node_detector=_model_detector(
            _model_item("upscale_models", "R-ESRGAN 4x+ Anime6B.pth"),
            kinds=("upscale_models",),
        ),
    )
    cube = cube_state(
        nodes={
            "vectorscopecc": {
                "class_type": "VectorscopeCC",
                "inputs": {
                    "model_name": "R-ESRGAN 4x+ Anime6B.pth",
                    "brightness": 0.5,
                },
            }
        },
        definitions={
            "VectorscopeCC": {
                "input": {
                    "required": {
                        "model_name": [
                            ["R-ESRGAN 4x+ Anime6B.pth"],
                            {},
                        ],
                        "brightness": ["FLOAT", {"min": 0, "max": 1, "step": 0.01}],
                    }
                },
            }
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["vectorscopecc"].card.icon_name == (
        "palette"
    )


def test_build_snapshot_without_model_detector_leaves_model_host_uniconed() -> None:
    """Default behavior should remain unchanged when no detector is composed."""

    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {"options": ["R-ESRGAN 4x+ Anime6B.pth"]},
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
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
        },
    )

    assert (
        snapshot.resolved_nodes_by_alias["A"]["load_upscale_model"].card.icon_name
        is None
    )


def test_build_snapshot_does_not_icon_non_model_list_node() -> None:
    """Ordinary LIST hosts should not receive the model icon."""

    service = NodeBehaviorService(
        node_definition_gateway=DummyNodeDefinitionGateway(),
        model_backed_node_detector=_model_detector(
            _model_item("checkpoints", "SDXL/base.safetensors"),
            kinds=("checkpoints",),
        ),
    )
    cube = cube_state(
        nodes={
            "mode_selector": {
                "class_type": "ModeSelector",
                "inputs": {"mode": "fast"},
            }
        },
        definitions={
            "ModeSelector": {
                "input": {"required": {"mode": [["fast", "accurate"], {}]}},
            }
        },
    )

    snapshot = service.build_snapshot(cube_states={"A": cube}, stack_order=["A"])

    assert snapshot.resolved_nodes_by_alias["A"]["mode_selector"].card.icon_name is None
