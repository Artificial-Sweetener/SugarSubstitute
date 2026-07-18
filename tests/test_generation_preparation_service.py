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

"""Tests for application-level generation snapshot preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationPreparationService,
    GenerationRequest,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.prompt_wildcards import PromptWildcardPreprocessingContext
from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.comfy_workflow import DirectWorkflowState
from tests.headless_direct_scene_preparation_harness import (
    HeadlessDirectScenePreparationHarness,
)
from tests.prompt_detection_fixture_catalog import (
    deterministic_prompt_detection_fixtures,
)


class _RecipeSerializer:
    """Record plan and serialize calls while rendering prompt overlay values."""

    def __init__(self) -> None:
        """Initialize call counters."""

        self.context_calls = 0
        self.plan_calls = 0
        self.serialize_calls: list[Mapping[tuple[str, str, str], object]] = []

    def create_serialization_context(self) -> object:
        """Return a stable fake serialization context."""

        self.context_calls += 1
        return object()

    def build_serialization_plan(
        self,
        workflow: object,
        *,
        enabled_node_keys_by_alias: Mapping[str, tuple[str, ...]] | None = None,
        disabled_node_keys_by_alias: Mapping[str, tuple[str, ...]] | None = None,
        serialization_context: object | None = None,
    ) -> object:
        """Return a stable fake plan while recording call count."""

        _ = workflow, enabled_node_keys_by_alias, disabled_node_keys_by_alias
        assert serialization_context is not None
        self.plan_calls += 1
        return object()

    def serialize_workflow_to_sugar_script(
        self,
        workflow: object,
        *,
        prompt_field_overrides: Mapping[tuple[str, str, str], object] | None = None,
        serialization_context: object | None = None,
        serialization_plan: object | None = None,
    ) -> str:
        """Render prompt text from overlays for assertions."""

        assert serialization_context is not None
        assert serialization_plan is not None
        overrides = prompt_field_overrides or {}
        self.serialize_calls.append(overrides)
        workflow_state = cast(Any, workflow)
        base_prompt = workflow_state.cubes["Text"].buffer["nodes"]["positive_prompt"][
            "inputs"
        ]["text"]
        prompt = overrides.get(("Text", "positive_prompt", "text"), base_prompt)
        return f"# prompt={prompt!r}"


class _ResolvedWildcardPreprocessor:
    """Resolve one deterministic wildcard marker in prompt-field overlays."""

    def resolve_workflow_prompt_field_overrides(
        self,
        *,
        workflow: object,
        workflow_id: str,
        prompt_field_overrides: Mapping[tuple[str, str, str], str] | None = None,
        preprocessing_context: PromptWildcardPreprocessingContext | None = None,
        prompt_endpoint_index: PromptEndpointIndex | None = None,
    ) -> dict[tuple[str, str, str], str]:
        """Return overlays with the deterministic test marker resolved."""

        _ = workflow, workflow_id, preprocessing_context, prompt_endpoint_index
        return {
            locator: value.replace("__color__", "crimson")
            for locator, value in (prompt_field_overrides or {}).items()
        }


def test_captured_generation_request_detaches_live_workflow() -> None:
    """Captured requests should not observe later edits to the live workflow."""

    workflow = _scene_workflow()
    request = GenerationRequest(
        workflow_id="wf",
        workflow_name="Recipe",
        workflow=cast(Any, workflow),
    )
    behavior_snapshot = _behavior_snapshot()

    captured = CapturedGenerationRequest.capture(
        request=request,
        behavior_snapshot=behavior_snapshot,
    )
    workflow_for_mutation = cast(Any, workflow)
    workflow_for_mutation.cubes["Text"].buffer["nodes"]["positive_prompt"]["inputs"][
        "text"
    ] = "mutated"

    captured_workflow = cast(Any, captured.workflow)
    captured_prompt = captured_workflow.cubes["Text"].buffer["nodes"][
        "positive_prompt"
    ]["inputs"]["text"]
    assert captured_prompt.startswith("quality")


def test_generation_preparation_service_reuses_plan_across_scene_snapshots() -> None:
    """Multi-scene preparation should build one plan and serialize each scene."""

    serializer = _RecipeSerializer()
    service = GenerationPreparationService(recipe_io_service=serializer)
    captured = CapturedGenerationRequest.capture(
        request=GenerationRequest(
            workflow_id="wf",
            workflow_name="Recipe",
            workflow=cast(Any, _scene_workflow()),
        ),
        behavior_snapshot=_behavior_snapshot(),
    )

    result = service.prepare_queued_snapshots(
        request=captured, scene_run_id="scene-run"
    )

    assert serializer.context_calls == 1
    assert serializer.plan_calls == 1
    assert len(serializer.serialize_calls) == 2
    assert [snapshot.workflow_name for snapshot in result.snapshots] == [
        "Recipe - portrait",
        "Recipe - cafe",
    ]
    assert [snapshot.sugar_script_text for snapshot in result.snapshots] == [
        "# prompt='quality\\n\\nportrait'",
        "# prompt='quality\\n\\ncafe'",
    ]
    assert result.scene_run_id == "scene-run"
    assert result.scene_count == 2


def test_generation_preparation_builds_direct_comfy_graph_without_sugar() -> None:
    """A direct workflow should snapshot an API graph without recipe serialization."""

    serializer = _RecipeSerializer()
    service = GenerationPreparationService(recipe_io_service=serializer)
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("workflow.json"),
            source_workflow={"nodes": [], "links": []},
            buffer={
                "nodes": {
                    "4": {
                        "class_type": "KSampler",
                        "inputs": {"seed": 42},
                        "mode": 0,
                    }
                }
            },
        )
    )
    captured = CapturedGenerationRequest.capture(
        request=GenerationRequest(
            workflow_id="wf",
            workflow_name="Direct",
            workflow=cast(Any, workflow),
        ),
        behavior_snapshot=None,
    )

    result = service.prepare_queued_snapshots(request=captured)

    assert serializer.context_calls == 0
    assert serializer.plan_calls == 0
    assert serializer.serialize_calls == []
    assert result.snapshots[0].sugar_script_text == ""
    assert result.snapshots[0].direct_workflow_plan is not None
    assert result.snapshots[0].direct_workflow_plan.authored_api_graph == {
        "4": {"class_type": "KSampler", "inputs": {"seed": 42}}
    }


def test_generation_preparation_projects_direct_prompt_scenes_without_sugar() -> None:
    """Direct scenes should alter detached Comfy inputs and reuse output intent."""

    serializer = _RecipeSerializer()
    service = GenerationPreparationService(recipe_io_service=serializer)
    document = DirectWorkflowState(
        source_path=Path("workflow.json"),
        source_workflow={"nodes": [], "links": []},
        buffer={
            "nodes": {
                "prompt": {
                    "class_type": "String",
                    "inputs": {"text": "quality\n**portrait\nportrait\n**cafe\ncafe"},
                    "mode": 0,
                }
            }
        },
    )
    workflow = WorkflowState(direct_workflow=document)
    behavior_snapshot = EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=PromptEndpointIndex.from_endpoints(
            (
                PromptEndpoint(
                    cube_alias=DIRECT_WORKFLOW_SECTION_KEY,
                    role=PromptRole.POSITIVE,
                    node_name="prompt",
                    field_key="text",
                ),
            )
        ),
    )
    captured = CapturedGenerationRequest.capture(
        request=GenerationRequest(
            workflow_id="wf",
            workflow_name="Direct",
            workflow=cast(Any, workflow),
        ),
        behavior_snapshot=behavior_snapshot,
    )

    result = service.prepare_queued_snapshots(
        request=captured,
        scene_run_id="direct-scenes",
    )

    assert serializer.context_calls == 0
    assert serializer.plan_calls == 0
    assert result.scene_run_id == "direct-scenes"
    assert result.scene_count == 2
    assert [snapshot.scene_key for snapshot in result.snapshots] == [
        "portrait",
        "cafe",
    ]
    assert [
        cast(Any, snapshot.direct_workflow_plan.authored_api_graph)["prompt"]["inputs"][
            "text"
        ]
        for snapshot in result.snapshots
        if snapshot.direct_workflow_plan is not None
    ] == ["quality\n\nportrait", "quality\n\ncafe"]
    assert cast(Any, document.buffer)["nodes"]["prompt"]["inputs"]["text"].startswith(
        "quality\n**portrait"
    )


def test_primitive_prompt_scenes_lower_through_real_sdxl_fixture() -> None:
    """Primitive prompt scenes should fan out through the normal Comfy lowering path."""

    repository_root = Path(__file__).resolve().parents[1]
    fixture = deterministic_prompt_detection_fixtures(repository_root)[0]
    positive_text = "quality\n**portrait\n__color__ hair\n**cafe\nblue hair"
    negative_text = "bad\n**portrait\nblurry\n**cafe\nwatermark"
    result, document = HeadlessDirectScenePreparationHarness(
        wildcard_preprocessor=_ResolvedWildcardPreprocessor()
    ).prepare(
        fixture,
        prompt_text_by_node={"51": positive_text, "50": negative_text},
        scene_run_id="sdxl-scenes",
    )
    mutable_buffer = cast(Any, document.buffer)

    assert result.scene_count == 2
    expected_scene_prompts = (
        ("quality\n\ncrimson hair", "bad\n\nblurry"),
        ("quality\n\nblue hair", "bad\n\nwatermark"),
    )
    for snapshot, (expected_positive, expected_negative) in zip(
        result.snapshots,
        expected_scene_prompts,
        strict=True,
    ):
        assert snapshot.direct_workflow_plan is not None
        graph = cast(Any, snapshot.direct_workflow_plan.authored_api_graph)
        assert "50" not in graph
        assert "51" not in graph
        assert graph["6"]["inputs"]["text"] == expected_positive
        assert graph["15"]["inputs"]["text"] == expected_positive
        assert graph["7"]["inputs"]["text"] == expected_negative
        assert graph["16"]["inputs"]["text"] == expected_negative
    assert mutable_buffer["nodes"]["51"]["inputs"]["text"] == positive_text
    assert mutable_buffer["nodes"]["50"]["inputs"]["text"] == negative_text


def _scene_workflow() -> WorkflowState:
    """Return a workflow with two runnable prompt scenes."""

    return WorkflowState(
        stack_order=["Text"],
        cubes={
            "Text": CubeState(
                cube_id="cube",
                version="1.0.0",
                alias="Text",
                original_cube={},
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "class_type": "String",
                            "inputs": {
                                "text": "quality\n**portrait\nportrait\n**cafe\ncafe"
                            },
                        }
                    }
                },
            )
        },
    )


def _behavior_snapshot() -> EditorBehaviorSnapshot:
    """Return a prompt endpoint snapshot for the test workflow."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=PromptEndpointIndex.from_endpoints(
            (
                PromptEndpoint(
                    cube_alias="Text",
                    role=PromptRole.POSITIVE,
                    node_name="positive_prompt",
                    field_key="text",
                ),
            )
        ),
    )
