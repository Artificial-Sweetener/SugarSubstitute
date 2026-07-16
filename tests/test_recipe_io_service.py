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

"""Contract tests for application recipe I/O orchestration service."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import substitute.application.recipes.recipe_io_service as recipe_io_module
from pytest import LogCaptureFixture

from substitute.application.ports.recipe_repository import LoadedRecipeDocument
from substitute.application.recipes import RecipeIoService
from substitute.domain.recipes import GlobalOverrideSerializationScope
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.workflow import CubeState


class _FakeRecipeRepository:
    """Simple in-memory recipe repository double for deterministic service tests."""

    def __init__(self) -> None:
        self.saved: list[tuple[Path, str, str]] = []
        self.loaded_path: Path | None = None

    def load_recipe_document(self, path: Path) -> LoadedRecipeDocument:
        """Return deterministic loaded document payload for parse-orchestration tests."""

        self.loaded_path = path
        return LoadedRecipeDocument(
            sugar_script_text=(
                'use "Artificial-Sweetener/Base-Cubes/Text to Image.cube" as A\n'
                "set *.*.seed = 7\n"
                '# global_override_selection {"key":"seed","selected":true}\n'
            ),
            source_path=path,
            source_kind="text",
        )

    def has_embedded_recipe_script(self, path: Path) -> bool:
        """Return deterministic PNG recipe sniffing results by filename."""

        return path.name == "embedded.png"

    def save_recipe_document(
        self,
        path: Path,
        *,
        project_name: str,
        sugar_script_text: str,
    ) -> None:
        """Capture save payload invoked by service orchestration."""

        self.saved.append((path, project_name, sugar_script_text))


class _FakeNodeDefinitionGateway:
    """Node-definition gateway double returning configured object-info payloads."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store live definitions by class type."""

        self._definitions = definitions
        self.required_calls: list[str] = []

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return non-blocking live definitions for protocol completeness."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return a Comfy object-info response shape for one node class."""

        self.required_calls.append(node_class)
        definition = self._definitions.get(node_class)
        return {node_class: definition} if definition is not None else {}


class _FakeCubeDefinitionProvider:
    """Cube definition provider double for SugarScript label resolution tests."""

    def __init__(self, graphs: dict[str, dict[str, object]]) -> None:
        """Store graphs keyed by cube id."""

        self._graphs = graphs

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> SimpleNamespace:
        """Return a loaded cube shape for latest-version recipe parsing."""

        _ = cube_load_trace_id
        return SimpleNamespace(graph=self._graphs[cube_id])

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> SimpleNamespace:
        """Return a loaded cube shape for pinned-version recipe parsing."""

        _ = version, cube_load_trace_id
        return self.load_cube_definition(cube_id)


class _FakeModelHashLookup:
    """Return deterministic recipe model hashes without slow collaborators."""

    def __init__(self, hashes: dict[tuple[str, str], str]) -> None:
        """Store hashes by model kind and backend value."""

        self.calls: list[tuple[str, str]] = []
        self._hashes = hashes

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return a configured hash for one model value."""

        self.calls.append((kind, value))
        return self._hashes.get((kind, value))


class _FakePromptLoraHashLookup:
    """Return deterministic inline prompt LoRA hashes for recipe saves."""

    def __init__(
        self,
        hashes: dict[str, str],
        *,
        backend_values: dict[str, str] | None = None,
    ) -> None:
        """Store hashes by prompt LoRA name."""

        self.calls: list[str] = []
        self._hashes = hashes
        self._backend_values = backend_values

    def hash_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return a configured hash for one prompt LoRA token name."""

        self.calls.append(prompt_name)
        return self._hashes.get(prompt_name)

    def backend_value_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return a configured backend value shape for protocol completeness."""

        if self._backend_values is not None:
            return self._backend_values.get(prompt_name)
        return prompt_name if prompt_name in self._hashes else None


def _labeled_upscale_graph() -> dict[str, object]:
    """Return a runtime graph with a labeled wrapper input."""

    wrapper_id = "77a3a6f3-813a-47da-b57d-50fcd211cc28"
    return {
        "cube_id": "upscale",
        "version": "1.0.0",
        "nodes": {
            "upscale_by_factor": {
                "class_type": wrapper_id,
                "inputs": {"value": 1.5},
            }
        },
        "inputs": {},
        "outputs": {},
        "layout": {},
        "definitions": {},
        "subgraphs": [
            {
                "id": wrapper_id,
                "name": "Upscale by Factor",
                "inputs": [
                    {
                        "name": "value",
                        "label": "Scale Factor",
                        "type": "FLOAT",
                        "linkIds": [1],
                    }
                ],
                "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
                "links": [],
                "nodes": [],
            }
        ],
        "surface": {
            "default_flavor_id": "default",
            "controls": [
                {
                    "control_id": "upscale_by_factor.value",
                    "symbol": "upscale_by_factor",
                    "input_name": "value",
                    "label": "Scale Factor",
                    "class_type": wrapper_id,
                    "value_type": "number",
                }
            ],
        },
    }


def test_recipe_io_service_serializes_and_saves_workflow() -> None:
    """Save orchestration should serialize workflow and pass payload to repository."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {"positive_prompt": {"inputs": {"prompt_template": "hello"}}},
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"seed": {"value": 1234, "mode": "global"}},
        global_override_selections={"seed": True, "scheduler": False},
    )

    service.save_workflow_recipe(
        Path("E:/recipes/recipe.sugar"),
        workflow_name="My Recipe",
        workflow=workflow,
    )

    assert len(repository.saved) == 1
    path, project_name, recipe_text = repository.saved[0]
    assert path == Path("E:/recipes/recipe.sugar")
    assert project_name == "My Recipe"
    assert (
        'use "Artificial-Sweetener/Base-Cubes/Text to Image.cube"@1.0.0 as A'
        in recipe_text
    )
    assert "set *.*.seed = 1234" in recipe_text
    assert '# global_override_selection {"key":"scheduler","selected":false}' in (
        recipe_text
    )
    assert '# global_override_selection {"key":"seed","selected":true}' in recipe_text


def test_recipe_io_service_serializes_known_model_hash_comment() -> None:
    """Recipe saving should inject cache-known model hashes without slow lookups."""

    repository = _FakeRecipeRepository()
    lookup = _FakeModelHashLookup({("checkpoints", "base.safetensors"): "A" * 64})
    service = RecipeIoService(recipe_repository=repository, model_hash_lookup=lookup)
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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


def test_recipe_serialization_plan_matches_direct_serialization() -> None:
    """Plan rendering should preserve direct serializer output byte-for-byte."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "hello"},
                }
            },
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"seed": {"value": 123, "mode": "global"}},
        global_override_selections={"seed": True},
    )

    direct_recipe_text = service.serialize_workflow_to_sugar_script(workflow)
    context = service.create_serialization_context()
    plan = service.build_serialization_plan(
        workflow,
        serialization_context=context,
    )
    planned_recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        serialization_context=context,
        serialization_plan=plan,
    )

    assert planned_recipe_text == direct_recipe_text


def test_recipe_serialization_plan_renders_prompt_overrides_without_mutating_base() -> (
    None
):
    """Prompt overlays should affect one render without changing plan buffers."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "prompt": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "base prompt"},
                }
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

    overlay_recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        serialization_context=context,
        serialization_plan=plan,
        prompt_field_overrides={("A", "prompt", "text"): "scene prompt"},
    )
    base_recipe_text = service.serialize_workflow_to_sugar_script(
        workflow,
        serialization_context=context,
        serialization_plan=plan,
    )

    assert 'set A.prompt.text = "scene prompt"' in overlay_recipe_text
    assert 'set A.prompt.text = "base prompt"' in base_recipe_text
    base_nodes = cast(dict[str, Any], plan.base_prepared_buffers["A"]["nodes"])
    base_prompt = cast(dict[str, Any], base_nodes["prompt"])
    base_inputs = cast(dict[str, Any], base_prompt["inputs"])
    assert base_inputs["text"] == "base prompt"


def test_recipe_serialization_plan_reuses_strip_and_label_work(
    monkeypatch: Any,
) -> None:
    """Repeated plan renders should not rebuild base strip or label data."""

    strip_calls: list[int] = []
    label_calls: list[int] = []
    original_strip_recipe_buffers = recipe_io_module.strip_recipe_buffers
    original_from_cube_graphs = recipe_io_module.SugarScriptLabelIndex.from_cube_graphs

    def _counting_strip_recipe_buffers(
        ordered_aliases: object,
        cube_states: object,
    ) -> object:
        """Count strip calls while delegating to the real implementation."""

        strip_calls.append(1)
        return original_strip_recipe_buffers(ordered_aliases, cube_states)  # type: ignore[arg-type]

    def _counting_from_cube_graphs(
        cls: type[object],
        cube_graphs_by_alias: object,
    ) -> object:
        """Count label-index builds while delegating to the real implementation."""

        _ = cls
        label_calls.append(1)
        return original_from_cube_graphs(cube_graphs_by_alias)  # type: ignore[arg-type]

    monkeypatch.setattr(
        recipe_io_module,
        "strip_recipe_buffers",
        _counting_strip_recipe_buffers,
    )
    monkeypatch.setattr(
        recipe_io_module.SugarScriptLabelIndex,
        "from_cube_graphs",
        classmethod(_counting_from_cube_graphs),
    )
    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = CubeState(
        cube_id="cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={"nodes": {"prompt": {"inputs": {"text": "hello"}}}},
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

    service.serialize_workflow_to_sugar_script(
        workflow,
        serialization_context=context,
        serialization_plan=plan,
    )
    service.serialize_workflow_to_sugar_script(
        workflow,
        serialization_context=context,
        serialization_plan=plan,
    )

    assert strip_calls == [1]
    assert label_calls == [1]


def test_recipe_io_service_preserves_escaped_prompt_source_in_recipe_text() -> None:
    """Recipe serialization should persist escaped prompt source instead of display text."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/Text to Image.cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "Artificial-Sweetener/Base-Cubes/Text to Image.cube",
            "nodes": {
                "positive_prompt": {
                    "inputs": {"prompt_template": r"painting \(medium\)"}
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

    assert len(repository.saved) == 1
    _, _, recipe_text = repository.saved[0]
    assert (
        'set A.positive_prompt.prompt_template = "painting \\\\(medium\\\\)"'
        in recipe_text
    )


def test_recipe_io_service_serializes_with_policy_disabled_nodes() -> None:
    """Generation serialization should honor resolved-disabled node policy."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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


def test_recipe_io_service_serializes_and_parses_visible_cube_labels() -> None:
    """Recipe IO should write visible labels and restore machine keys on parse."""

    graph = _labeled_upscale_graph()
    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        cube_definition_provider=_FakeCubeDefinitionProvider({"upscale": graph}),
    )
    cube = CubeState(
        cube_id="upscale",
        version="1.0.0",
        alias="A",
        original_cube=graph,
        buffer=graph,
    )
    workflow = SimpleNamespace(
        stack_order=["A"], cubes={"A": cube}, global_overrides={}
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)
    parsed = service.parse_recipe_script(recipe_text)
    parsed_a = cast(dict[str, Any], parsed.buffers["A"])
    parsed_nodes = cast(dict[str, Any], parsed_a["nodes"])
    parsed_upscale = cast(dict[str, Any], parsed_nodes["upscale_by_factor"])
    parsed_inputs = cast(dict[str, Any], parsed_upscale["inputs"])

    assert 'set A."Upscale by Factor"."Scale Factor" = 1.5' in recipe_text
    assert parsed_inputs["value"] == 1.5


def test_recipe_io_service_serializes_seed_control_state() -> None:
    """Workflow-owned seed control state should be included in saved recipes."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = CubeState(
        cube_id="sampler",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "sampler",
            "nodes": {
                "ksampler": {
                    "inputs": {
                        "seed": 1234,
                    }
                }
            },
        },
        field_control_states={"ksampler": {"seed": SeedControlState(SeedMode.FIXED)}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"seed": {"value": 1234, "mode": "global"}},
        global_override_selections={},
        override_control_states={"seed": SeedControlState(SeedMode.FIXED)},
    )

    recipe_text = service.serialize_workflow_to_sugar_script(workflow)

    assert (
        '# seed_control {"alias":"A","field":"seed","mode":"fixed","node":"ksampler"}'
        in recipe_text
    )
    assert '# global_override_seed_control {"key":"seed","mode":"fixed"}' in recipe_text


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
    cube = CubeState(
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


def test_recipe_serialization_context_reuses_required_node_definitions() -> None:
    """Required picker preflight should fetch each node class once per context."""

    gateway = _FakeNodeDefinitionGateway(
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
    )
    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        node_definition_gateway=gateway,
    )
    cube = CubeState(
        cube_id="cube",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "nodes": {
                "first_checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": ""},
                },
                "second_checkpoint": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": ""},
                },
            }
        },
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={},
    )
    context = service.create_serialization_context()

    service.build_serialization_plan(workflow, serialization_context=context)

    assert gateway.required_calls == ["CheckpointLoaderSimple"]


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
    cube = CubeState(
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
    cube = CubeState(
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
    cube = CubeState(
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


def test_recipe_io_service_load_and_parse_orchestration() -> None:
    """Load orchestration should return parsed buffers and preserve source metadata."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    source_path = Path("E:/recipes/loaded.sugar")

    parsed_recipe = service.load_and_parse_recipe_document(source_path)

    assert repository.loaded_path == source_path
    assert parsed_recipe.loaded_document.source_path == source_path
    assert parsed_recipe.parsed_script.global_overrides["seed"]["value"] == 7
    assert parsed_recipe.parsed_script.global_override_selections == {"seed": True}
    assert (
        parsed_recipe.parsed_script.buffers["A"]["cube_id"]
        == "Artificial-Sweetener/Base-Cubes/Text to Image.cube"
    )


def test_recipe_io_service_classifies_text_recipe_paths() -> None:
    """Only native Sugar recipe text paths should be accepted."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    sugar = service.classify_recipe_document(Path("E:/recipes/demo.sugar"))
    sugar_txt = service.classify_recipe_document(Path("E:/recipes/demo.sugar.txt"))
    txt = service.classify_recipe_document(Path("E:/recipes/demo.txt"))

    assert sugar.supported is True
    assert sugar.source_kind == "text"
    assert sugar_txt.supported is False
    assert sugar_txt.source_kind is None
    assert txt.supported is False
    assert txt.source_kind is None


def test_recipe_io_service_classifies_png_by_embedded_recipe_metadata() -> None:
    """PNG acceptance should depend on embedded Sugar recipe metadata."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    embedded = service.classify_recipe_document(Path("E:/recipes/embedded.png"))
    plain = service.classify_recipe_document(Path("E:/recipes/plain.png"))

    assert embedded.supported is True
    assert embedded.source_kind == "png"
    assert embedded.reason == "png_embedded_recipe"
    assert plain.supported is False
    assert plain.source_kind is None
    assert plain.reason == "png_without_embedded_recipe"


def test_recipe_io_service_rejects_unsupported_recipe_drop_paths() -> None:
    """Non-recipe extensions should not be classified as loadable recipes."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    classified = service.classify_recipe_document(Path("E:/images/plain.jpg"))

    assert classified.supported is False
    assert classified.source_kind is None
    assert classified.reason == "unsupported_extension"


def test_build_default_recipe_path_uses_script_scoped_recipe_location(
    tmp_path: Path,
) -> None:
    """Default recipe paths should stay inside the workflow-named script directory."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    destination = service.build_default_recipe_path("Recipe One", tmp_path)

    assert destination == (tmp_path / "Recipe One" / "Recipe One.sugar").resolve()


def test_validate_recipe_destination_accepts_paths_outside_script_root(
    tmp_path: Path,
) -> None:
    """Recipe destination validation should allow explicit paths outside script root."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    destination = service.validate_recipe_destination(
        tmp_path.parent / "external.sugar"
    )

    assert destination == (tmp_path.parent / "external.sugar").resolve()


def test_validate_recipe_destination_rejects_directory_paths(tmp_path: Path) -> None:
    """Recipe destination validation should reject directories."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    try:
        service.validate_recipe_destination(tmp_path)
    except ValueError as error:
        assert "Workflow recipe" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError(
            "Expected recipe destination validation to reject directory"
        )


def test_validate_recipe_destination_rejects_unsupported_extensions(
    tmp_path: Path,
) -> None:
    """Recipe destination validation should reject unsupported file extensions."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())

    try:
        service.validate_recipe_destination(tmp_path / "recipe.json")
    except ValueError as error:
        assert ".sugar" in str(error)
    else:  # pragma: no cover - assertion path only
        raise AssertionError("Expected recipe destination validation to reject suffix")


def test_save_workflow_recipe_to_default_path_returns_saved_destination(
    tmp_path: Path,
) -> None:
    """Default-path save should persist through the repository and return the final path."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    workflow = SimpleNamespace(stack_order=[], cubes={}, global_overrides={})

    destination = service.save_workflow_recipe_to_default_path(
        "Recipe Two",
        workflow,
        tmp_path,
    )

    assert destination == (tmp_path / "Recipe Two" / "Recipe Two.sugar").resolve()
    assert len(repository.saved) == 1
    saved_path, project_name, recipe_text = repository.saved[0]
    assert saved_path == destination
    assert project_name == "Recipe Two"
    assert recipe_text.strip() == ""
