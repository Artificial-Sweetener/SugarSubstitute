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

"""Test recipe input-policy contracts."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, cast

from _pytest.logging import LogCaptureFixture
from substitute.application.recipes import RecipeIoService
from substitute.domain.recipes import GlobalOverrideSerializationScope

from .support import (
    _FakeNodeDefinitionGateway,
    _FakeRecipeRepository,
    _canonical_test_cube_state,
)


def test_recipe_io_service_serializes_with_policy_disabled_nodes() -> None:
    """Generation serialization should honor resolved-disabled node policy."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Diffusion Upscale.cube",
        version="1.0.0",
        alias="Upscale",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Diffusion Upscale.cube",
            "nodes": {
                "checkpoint": {
                    "inputs": {"ckpt_name": "Anima\\ae.safetensors"},
                },
                "load_upscale_model": {
                    "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
                },
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["Upscale"],
        cubes={"Upscale": cube},
        global_overrides={},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        disabled_node_keys_by_alias={"Upscale": ("checkpoint",)},
    )

    assert "disable Upscale.checkpoint" in recipe_text
    assert "Anima" not in recipe_text
    assert "R-ESRGAN 4x+ Anime6B.pth" in recipe_text


def test_recipe_io_service_serializes_selected_inpaint_image_path(
    caplog: LogCaptureFixture,
) -> None:
    """Recipe serialization should include selected LoadImage values."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Inpaint.cube",
        version="2.0.0",
        alias="Inpaint",
        original_cube={},
        buffer={
            "nodes": {
                "load_image": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "E:/images/selected.png"},
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["Inpaint"],
        cubes={"Inpaint": cube},
        global_overrides={},
    )

    with caplog.at_level(
        logging.DEBUG,
        logger="sugarsubstitute.application.recipes.recipe_io_service",
    ):
        recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert 'set Inpaint.load_image.image = "E:/images/selected.png"' in recipe_text
    assert "00282-3430329909-ad-before.png" not in recipe_text
    assert "Serializing workflow image input" in caplog.text
    assert "image_value=E:/images/selected.png" in caplog.text


def test_recipe_io_service_forwards_global_override_scopes() -> None:
    """Recipe IO should pass active override scopes into the Sugar codec."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = _canonical_test_cube_state(
        cube_id="X",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={"nodes": {"sampler": {"inputs": {"sampler_name": "euler"}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"sampler_name": {"value": "heun", "mode": "global"}},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        global_override_scopes={
            "sampler_name": GlobalOverrideSerializationScope(
                override_key="sampler_name",
                value="heun",
                mode="global",
                full_participation=False,
                participant_fields=frozenset({("A", "sampler", "sampler_name")}),
            )
        },
    )

    assert "set *.*.sampler_name" not in recipe_text
    assert 'set A.sampler.sampler_name = "heun"' in recipe_text


def test_recipe_io_service_omits_blank_model_global_override() -> None:
    """Blank model overrides should remain unset in portable recipes."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = _canonical_test_cube_state(
        cube_id="X",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "nodes": {
                "checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {},
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"ckpt_name": {"value": "", "mode": "global"}},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert "ckpt_name" not in recipe_text


def test_recipe_io_service_omits_blank_model_override_scope() -> None:
    """Blank scoped model overrides should not serialize local assignments."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = _canonical_test_cube_state(
        cube_id="X",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "nodes": {
                "checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {},
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        global_override_scopes={
            "ckpt_name": GlobalOverrideSerializationScope(
                override_key="ckpt_name",
                value="",
                mode="global",
                full_participation=False,
                participant_fields=frozenset({("A", "checkpoint", "ckpt_name")}),
            )
        },
    )

    assert "ckpt_name" not in recipe_text


def test_serialize_workflow_omits_blank_model_picker_with_live_default() -> None:
    """Blank model selections remain portable instead of pinning a local default."""

    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                [
                                    r"Flux\flux1-dev-bnb-nf4.safetensors",
                                    r"Illustrious\amanatsuIllustrious_v11.safetensors",
                                ],
                                {
                                    "default": (
                                        r"Illustrious\amanatsuIllustrious_v11.safetensors"
                                    )
                                },
                            ]
                        }
                    }
                }
            }
        ),
    )
    cube = _canonical_test_cube_state(
        cube_id="cube",
        version="1.0.0",
        alias="SDXL/Text to Image",
        original_cube={},
        buffer={
            "nodes": {
                "checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": ""},
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["SDXL/Text to Image"],
        cubes={"SDXL/Text to Image": cube},
        global_overrides={},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert "ckpt_name" not in recipe_text
    nodes = cast(dict[str, Any], cube.buffer["nodes"])
    checkpoint = cast(dict[str, Any], nodes["checkpoint"])
    inputs = cast(dict[str, Any], checkpoint["inputs"])
    assert inputs["ckpt_name"] == ""


def test_serialize_workflow_omits_blank_model_picker_with_only_one_option() -> None:
    """A blank model selection is omitted even when one local model exists."""

    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                [r"Flux\flux1-dev-bnb-nf4.safetensors"],
                                {},
                            ]
                        }
                    }
                }
            }
        ),
    )
    cube = _canonical_test_cube_state(
        cube_id="cube",
        version="1.0.0",
        alias="SDXL/Text to Image",
        original_cube={},
        buffer={
            "nodes": {
                "checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": ""},
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["SDXL/Text to Image"],
        cubes={"SDXL/Text to Image": cube},
        global_overrides={},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert "ckpt_name" not in recipe_text

    nodes = cast(dict[str, Any], cube.buffer["nodes"])
    checkpoint = cast(dict[str, Any], nodes["checkpoint"])
    inputs = cast(dict[str, Any], checkpoint["inputs"])
    assert inputs["ckpt_name"] == ""


def test_serialize_workflow_preserves_explicit_amanatsu_checkpoint() -> None:
    """Explicit backend picker values should serialize unchanged."""

    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                [
                                    r"Flux\flux1-dev-bnb-nf4.safetensors",
                                    r"Illustrious\amanatsuIllustrious_v11.safetensors",
                                ],
                                {},
                            ]
                        }
                    }
                }
            }
        ),
    )
    cube = _canonical_test_cube_state(
        cube_id="cube",
        version="1.0.0",
        alias="SDXL/Text to Image",
        original_cube={},
        buffer={
            "nodes": {
                "checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {
                        "ckpt_name": r"Illustrious\amanatsuIllustrious_v11.safetensors"
                    },
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["SDXL/Text to Image"],
        cubes={"SDXL/Text to Image": cube},
        global_overrides={},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert (
        'set "SDXL/Text to Image".checkpoint.ckpt_name = '
        r'"Illustrious\\amanatsuIllustrious_v11.safetensors"'
    ) in recipe_text


def test_serialize_workflow_preserves_optional_blank_picker_values() -> None:
    """Optional blank pickers should keep current schema behavior."""

    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        node_definition_gateway=_FakeNodeDefinitionGateway(
            {
                "OptionalModelNode": {
                    "input": {
                        "required": {},
                        "optional": {"model_name": [[r"models\a.safetensors"], {}]},
                    }
                }
            }
        ),
    )
    cube = _canonical_test_cube_state(
        cube_id="cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "nodes": {
                "optional_model": {
                    "class_type": "OptionalModelNode",
                    "inputs": {"model_name": ""},
                }
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert 'set A.optional_model.model_name = ""' in recipe_text
