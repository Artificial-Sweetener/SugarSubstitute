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

"""Tests for generation-only prompt scene workflow materialization."""

from __future__ import annotations

from typing import Any, cast

import pytest
import substitute.application.generation.prompt_scene_preparation_plan as scene_plan_module

from substitute.application.generation import (
    PromptSceneMaterializationService,
    PromptScenePreparationPlanBuilder,
)
from substitute.application.prompt_editor import PromptSceneAnalysisService
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.domain.workflow import CubeState, WorkflowState


def test_scene_materialization_replaces_primary_positive_with_universal_and_scene() -> (
    None
):
    """Authority prompt should materialize universal text plus the selected scene."""

    workflow, endpoint_index = _workflow_with_prompt(
        "A",
        PromptRole.POSITIVE,
        "quality, {character}\n\n**portrait\nstudio portrait\n\n**cafe\nat cafe",
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    materialized = PromptSceneMaterializationService().materialize_workflow_for_scene(
        workflow=workflow,
        workflow_id="wf-1",
        scene_key="portrait",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert _prompt(materialized, "A") == "quality, {character}\n\nstudio portrait"
    assert _prompt(workflow, "A").startswith("quality, {character}\n\n**portrait")


def test_scene_materialization_applies_universal_negative_to_every_scene() -> None:
    """Prompt fields without scene markers should remain universal for every scene."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(
                positive="quality\n**portrait\nportrait\n**cafe\ncafe",
                negative="bad anatomy, blurry",
            )
        },
        stack_order=["A"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("A", PromptRole.NEGATIVE, "negative_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    materialized = PromptSceneMaterializationService().materialize_workflow_for_scene(
        workflow=workflow,
        workflow_id="wf-1",
        scene_key="cafe",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert _prompt(materialized, "A", "negative_prompt") == "bad anatomy, blurry"


def test_scene_materialization_appends_matching_secondary_scene_text() -> None:
    """Secondary independent prompt fields should append matching scene-local text."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(
                positive="quality\n**portrait\nportrait\n**cafe\ncafe",
                negative="bad anatomy\n**portrait\nextra fingers",
            )
        },
        stack_order=["A"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("A", PromptRole.NEGATIVE, "negative_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    materialized = PromptSceneMaterializationService().materialize_workflow_for_scene(
        workflow=workflow,
        workflow_id="wf-1",
        scene_key="portrait",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert _prompt(materialized, "A", "negative_prompt") == (
        "bad anatomy\n\nextra fingers"
    )


def test_scene_materialization_ignores_orphan_scene_blocks_for_authority_scenes() -> (
    None
):
    """Orphan blocks should not affect generated prompts for authority scenes."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(
                positive="quality\n**portrait\nportrait",
                negative="generic negative\n**hands\nbad hands",
            )
        },
        stack_order=["A"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("A", PromptRole.NEGATIVE, "negative_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    materialized = PromptSceneMaterializationService().materialize_workflow_for_scene(
        workflow=workflow,
        workflow_id="wf-1",
        scene_key="portrait",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert _prompt(materialized, "A", "negative_prompt") == "generic negative"


def test_scene_materialization_leaves_existing_linked_prompt_behavior_alone() -> None:
    """Linked prompt nodes should not be independently scene-materialized."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(positive="quality\n**portrait\nportrait"),
            "B": _cube(
                positive="linked local text\n**portrait\nshould stay",
                node_link={"from_cube": "A", "from_node": "positive_prompt"},
            ),
        },
        stack_order=["A", "B"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("B", PromptRole.POSITIVE, "positive_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    materialized = PromptSceneMaterializationService().materialize_workflow_for_scene(
        workflow=workflow,
        workflow_id="wf-1",
        scene_key="portrait",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert _prompt(materialized, "B") == "linked local text\n**portrait\nshould stay"


def test_scene_materialization_rejects_unknown_scene_keys() -> None:
    """Unknown scene keys should fail instead of producing ambiguous snapshots."""

    workflow, endpoint_index = _workflow_with_prompt(
        "A",
        PromptRole.POSITIVE,
        "**portrait\nportrait",
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    with pytest.raises(ValueError, match="Unknown workflow scene key"):
        PromptSceneMaterializationService().materialize_workflow_for_scene(
            workflow=workflow,
            workflow_id="wf-1",
            scene_key="missing",
            endpoint_index=endpoint_index,
            scene_analysis=analysis,
        )


def test_scene_preparation_plan_renders_scene_overrides_without_mutating_workflow() -> (
    None
):
    """Scene plans should render materialized prompt text as field overlays."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(
                positive="quality\n**portrait\nportrait\n**cafe\ncafe",
                negative="bad anatomy\n**portrait\nextra fingers",
            )
        },
        stack_order=["A"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("A", PromptRole.NEGATIVE, "negative_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    plan = PromptScenePreparationPlanBuilder().build(
        workflow=workflow,
        workflow_id="wf-1",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert plan.prompt_field_overrides_for_scene("portrait") == {
        ("A", "positive_prompt", "text"): "quality\n\nportrait",
        ("A", "negative_prompt", "text"): "bad anatomy\n\nextra fingers",
    }
    assert plan.prompt_field_overrides_for_scene("cafe") == {
        ("A", "positive_prompt", "text"): "quality\n\ncafe",
        ("A", "negative_prompt", "text"): "bad anatomy",
    }
    assert _prompt(workflow, "A") == "quality\n**portrait\nportrait\n**cafe\ncafe"


def test_scene_preparation_plan_skips_linked_prompt_endpoints() -> None:
    """Scene plans should keep linked prompt endpoint text out of overlays."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(positive="quality\n**portrait\nportrait"),
            "B": _cube(
                positive="linked local text\n**portrait\nshould stay",
                node_link={"from_cube": "A", "from_node": "positive_prompt"},
            ),
        },
        stack_order=["A", "B"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("B", PromptRole.POSITIVE, "positive_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )

    plan = PromptScenePreparationPlanBuilder().build(
        workflow=workflow,
        workflow_id="wf-1",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )

    assert plan.prompt_field_overrides_for_scene("portrait") == {
        ("A", "positive_prompt", "text"): "quality\n\nportrait",
    }


def test_scene_preparation_plan_parses_prompt_fields_once(monkeypatch: Any) -> None:
    """Rendering multiple scenes should not reparse prompt scene documents."""

    workflow = WorkflowState(
        cubes={
            "A": _cube(
                positive="quality\n**portrait\nportrait\n**cafe\ncafe",
                negative="bad anatomy\n**portrait\nextra fingers",
            )
        },
        stack_order=["A"],
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            _endpoint("A", PromptRole.POSITIVE, "positive_prompt"),
            _endpoint("A", PromptRole.NEGATIVE, "negative_prompt"),
        )
    )
    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoint_index,
    )
    original_parse = cast(
        Any,
        getattr(scene_plan_module, "parse_prompt_scene_document"),
    )
    parsed_texts: list[str] = []

    def _counting_parse(text: str) -> object:
        """Count parse calls while delegating to the real parser."""

        parsed_texts.append(text)
        return original_parse(text)

    monkeypatch.setattr(
        scene_plan_module,
        "parse_prompt_scene_document",
        _counting_parse,
    )

    plan = PromptScenePreparationPlanBuilder().build(
        workflow=workflow,
        workflow_id="wf-1",
        endpoint_index=endpoint_index,
        scene_analysis=analysis,
    )
    plan.prompt_field_overrides_for_scene("portrait")
    plan.prompt_field_overrides_for_scene("cafe")

    assert parsed_texts == [
        "quality\n**portrait\nportrait\n**cafe\ncafe",
        "bad anatomy\n**portrait\nextra fingers",
    ]


def _workflow_with_prompt(
    cube_alias: str,
    role: PromptRole,
    text: str,
) -> tuple[WorkflowState, PromptEndpointIndex]:
    """Return a one-cube workflow with one prompt endpoint."""

    node_name = f"{role.value}_prompt"
    cube = _cube(positive=text) if role is PromptRole.POSITIVE else _cube(negative=text)
    workflow = WorkflowState(
        cubes={cube_alias: cube},
        stack_order=[cube_alias],
    )
    return workflow, PromptEndpointIndex.from_endpoints(
        (_endpoint(cube_alias, role, node_name),)
    )


def _cube(
    *,
    positive: str = "",
    negative: str = "",
    node_link: dict[str, str] | None = None,
) -> CubeState:
    """Return a cube with positive and negative prompt nodes."""

    positive_node: dict[str, Any] = {
        "class_type": "Prompt",
        "inputs": {"text": positive},
    }
    if node_link is not None:
        positive_node["node_link"] = node_link
    return CubeState(
        cube_id="test",
        version="1",
        alias="test",
        original_cube={},
        buffer={
            "nodes": {
                "positive_prompt": positive_node,
                "negative_prompt": {
                    "class_type": "Prompt",
                    "inputs": {"text": negative},
                },
            }
        },
    )


def _endpoint(
    cube_alias: str,
    role: PromptRole,
    node_name: str,
) -> PromptEndpoint:
    """Return the test prompt endpoint for a prompt node."""

    return PromptEndpoint(
        cube_alias=cube_alias,
        role=role,
        node_name=node_name,
        field_key="text",
    )


def _prompt(
    workflow: WorkflowState,
    cube_alias: str,
    node_name: str = "positive_prompt",
) -> str:
    """Return prompt text from a test workflow."""

    nodes = cast(dict[str, Any], workflow.cubes[cube_alias].buffer["nodes"])
    node = cast(dict[str, Any], nodes[node_name])
    inputs = cast(dict[str, Any], node["inputs"])
    value = inputs["text"]
    assert isinstance(value, str)
    return value
