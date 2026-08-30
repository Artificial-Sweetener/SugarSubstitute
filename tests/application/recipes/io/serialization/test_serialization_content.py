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

"""Test recipe serialization-content contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.application.recipes import RecipeIoService
import substitute.application.recipes.recipe_io_service as recipe_io_module
from substitute.domain.generation.seed_control import SeedControlState, SeedMode

from .support import (
    _FakeCubeDefinitionProvider,
    _FakeNodeDefinitionGateway,
    _FakeRecipeRepository,
    _canonical_test_cube_state,
    _labeled_upscale_graph,
)


def test_recipe_io_service_serializes_and_saves_workflow() -> None:
    """Save orchestration should serialize workflow and pass payload to repository."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = _canonical_test_cube_state(
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


def test_recipe_serialization_plan_matches_direct_serialization() -> None:
    """Plan rendering should preserve direct serializer output byte-for-byte."""

    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
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
    original_strip_recipe_buffers = cast(
        Any,
        getattr(recipe_io_module, "strip_recipe_buffers"),
    )
    label_index_class = cast(Any, getattr(recipe_io_module, "SugarScriptLabelIndex"))
    original_from_cube_graphs = cast(Any, label_index_class.from_cube_graphs)

    def _counting_strip_recipe_buffers(
        ordered_aliases: object,
        cube_states: object,
    ) -> object:
        """Count strip calls while delegating to the real implementation."""

        strip_calls.append(1)
        return original_strip_recipe_buffers(ordered_aliases, cube_states)

    def _counting_from_cube_graphs(
        cls: type[object],
        cube_graphs_by_alias: object,
    ) -> object:
        """Count label-index builds while delegating to the real implementation."""

        _ = cls
        label_calls.append(1)
        return original_from_cube_graphs(cube_graphs_by_alias)

    monkeypatch.setattr(
        recipe_io_module,
        "strip_recipe_buffers",
        _counting_strip_recipe_buffers,
    )
    monkeypatch.setattr(
        label_index_class,
        "from_cube_graphs",
        classmethod(_counting_from_cube_graphs),
    )
    service = RecipeIoService(recipe_repository=_FakeRecipeRepository())
    cube = _canonical_test_cube_state(
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
    cube = _canonical_test_cube_state(
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


def test_recipe_io_service_preserves_escaped_prompt_source_in_recipe_text() -> None:
    """Recipe serialization should persist escaped prompt source instead of display text."""

    repository = _FakeRecipeRepository()
    service = RecipeIoService(recipe_repository=repository)
    cube = _canonical_test_cube_state(
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


def test_recipe_io_service_serializes_and_parses_visible_cube_labels() -> None:
    """Recipe IO should write visible labels and restore machine keys on parse."""

    graph = _labeled_upscale_graph()
    service = RecipeIoService(
        recipe_repository=_FakeRecipeRepository(),
        cube_definition_provider=_FakeCubeDefinitionProvider({"upscale": graph}),
    )
    cube = _canonical_test_cube_state(
        cube_id="upscale", version="1.0.0", alias="A", original_cube=graph, buffer=graph
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
    cube = _canonical_test_cube_state(
        cube_id="sampler",
        version="1.0.0",
        alias="A",
        original_cube={},
        buffer={
            "cube_id": "sampler",
            "nodes": {"ksampler": {"inputs": {"seed": 1234}}},
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
