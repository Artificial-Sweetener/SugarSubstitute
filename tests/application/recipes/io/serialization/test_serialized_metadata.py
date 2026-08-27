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

"""Test recipe serialized-metadata contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.recipes import RecipeIoService

from .support import (
    _FakeModelHashLookup,
    _FakePromptLoraHashLookup,
    _FakeRecipeRepository,
    _canonical_test_cube_state,
)


def test_recipe_io_service_serializes_known_model_hash_comment() -> None:
    """Recipe saving should inject cache-known model hashes without slow lookups."""

    repository = _FakeRecipeRepository()
    lookup = _FakeModelHashLookup({("checkpoints", "base.safetensors"): "A" * 64})
    service = RecipeIoService(recipe_repository=repository, model_hash_lookup=lookup)
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "base.safetensors"},
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    _, _, recipe_text = repository.saved[0]
    assert lookup.calls == [("checkpoints", "base.safetensors")]
    assert (
        f'set A.checkpoint.ckpt_name = "base.safetensors"\n# sha256 {"A" * 64}'
    ) in recipe_text


def test_recipe_io_service_serializes_anima_diffusion_model_hash_comment() -> None:
    """Anima diffusion model pickers should serialize eligible CivitAI hashes."""

    model_value = r"Anima\anima_base_V10.safetensors"
    repository = _FakeRecipeRepository()
    lookup = _FakeModelHashLookup({("diffusion_models", model_value): "B" * 64})
    service = RecipeIoService(recipe_repository=repository, model_hash_lookup=lookup)
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Anima Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Anima Text to Image.cube",
            "nodes": {
                "Models": {
                    "class_type": "SimpleSyrup.SimpleLoadAnima",
                    "inputs": {"diffusion_model": model_value},
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    _, _, recipe_text = repository.saved[0]
    assert lookup.calls == [("diffusion_models", model_value)]
    assert (
        f'set A.Models.diffusion_model = "Anima\\\\anima_base_V10.safetensors"\n'
        f"# sha256 {'B' * 64}"
    ) in recipe_text


def test_recipe_io_service_serializes_inline_prompt_lora_hash_comments() -> None:
    """Recipe saving should inject cache-known inline prompt LoRA hashes."""

    repository = _FakeRecipeRepository()
    lookup = _FakePromptLoraHashLookup(
        {
            "characters/midna": "a" * 64,
            "styles/ink": "B" * 64,
        }
    )
    service = RecipeIoService(
        recipe_repository=repository,
        prompt_lora_hash_lookup=lookup,
    )
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": ("<lora:characters/midna:0.80>, <lora:styles/ink:1.00>")
                    },
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    _, _, recipe_text = repository.saved[0]
    first_sha256 = "A" * 64
    second_sha256 = "B" * 64
    assert lookup.calls == ["characters/midna", "styles/ink"]
    assert (
        'set A.prompt.text = "<lora:characters/midna:0.80>, '
        '<lora:styles/ink:1.00>"\n'
        f'# lora_sha256 {{"name":"characters/midna","sha256":"{first_sha256}"}}\n'
        f'# lora_sha256 {{"name":"styles/ink","sha256":"{second_sha256}"}}'
    ) in recipe_text


def test_recipe_io_service_serializes_canonical_inline_prompt_lora_names() -> None:
    """Recipe serialization should use canonical backend LoRA names when known."""

    repository = _FakeRecipeRepository()
    lookup = _FakePromptLoraHashLookup(
        {"NoobAI/Bridge Tools Line Weight": "A" * 64},
        backend_values={
            "ILLUSTRIOUS\\CONCEPTS\\Bridge Tools Line Weight": (
                "NoobAI/Bridge Tools Line Weight.safetensors"
            )
        },
    )
    service = RecipeIoService(
        recipe_repository=repository,
        prompt_lora_hash_lookup=lookup,
    )
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": (
                            "<lora:ILLUSTRIOUS\\CONCEPTS\\Bridge Tools Line Weight:0.25>"
                        )
                    },
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    _, _, recipe_text = repository.saved[0]
    assert (
        'set A.prompt.text = "<lora:NoobAI/Bridge Tools Line Weight:0.25>"'
        in recipe_text
    )
    assert (
        "# lora_sha256 "
        '{"name":"NoobAI/Bridge Tools Line Weight","sha256":"AAAAAAAAAAAAAAAA'
    ) in recipe_text


def test_recipe_io_service_deduplicates_inline_prompt_lora_hash_comments() -> None:
    """Duplicate inline LoRA prompt names should emit one hash comment per field."""

    repository = _FakeRecipeRepository()
    lookup = _FakePromptLoraHashLookup({"characters/midna": "A" * 64})
    service = RecipeIoService(
        recipe_repository=repository,
        prompt_lora_hash_lookup=lookup,
    )
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": (
                            "<lora:characters/midna:0.80>, "
                            "<lora:characters\\midna.safetensors:1.00>"
                        )
                    },
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    _, _, recipe_text = repository.saved[0]
    assert lookup.calls == ["characters/midna"]
    assert recipe_text.count("# lora_sha256") == 1


def test_recipe_io_service_skips_unknown_inline_prompt_lora_hashes() -> None:
    """Inline LoRA tokens without eligible hashes should not emit metadata."""

    repository = _FakeRecipeRepository()
    lookup = _FakePromptLoraHashLookup({})
    service = RecipeIoService(
        recipe_repository=repository,
        prompt_lora_hash_lookup=lookup,
    )
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "<lora:unknown:1.00>"},
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    _, _, recipe_text = repository.saved[0]
    assert lookup.calls == ["unknown"]
    assert "# lora_sha256" not in recipe_text


def test_recipe_serialization_context_reuses_prompt_lora_text_hashes() -> None:
    """Repeated exact prompt text should reuse LoRA hash comments from context."""

    lookup = _FakePromptLoraHashLookup({"characters/midna": "A" * 64})
    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        prompt_lora_hash_lookup=lookup,
    )
    prompt_text = "<lora:characters/midna:1.00>"
    cube = _canonical_test_cube_state(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "first_prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": prompt_text},
                },
                "second_prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": prompt_text},
                },
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )
    context = service.create_serialization_context()
    plan = service.build_serialization_plan(
        workflow,
        serialization_context=context,
    )

    recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        serialization_context=context,
        serialization_plan=plan,
    )

    assert lookup.calls == ["characters/midna"]
    assert recipe_text.count("# lora_sha256") == 2
