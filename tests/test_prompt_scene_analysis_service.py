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

"""Tests for workflow-level prompt scene analysis."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.prompt_editor import PromptSceneAnalysisService
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole


def test_scene_analysis_uses_first_positive_prompt_as_authority() -> None:
    """Authority scenes should come from the first positive prompt in stack order."""

    workflow = _workflow(
        stack_order=["Negative", "Text", "Detailer"],
        prompts={
            ("Negative", "negative_prompt"): "bad anatomy",
            ("Text", "positive_prompt"): "quality\n**portrait\nportrait\n**cafe\ncafe",
            ("Detailer", "positive_prompt"): "**portrait\ndetail portrait",
        },
    )
    endpoints = _endpoints(
        ("Negative", PromptRole.NEGATIVE, "negative_prompt"),
        ("Text", PromptRole.POSITIVE, "positive_prompt"),
        ("Detailer", PromptRole.POSITIVE, "positive_prompt"),
    )

    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoints,
    )

    assert analysis.authority_endpoint == endpoints.endpoint_for(
        "Text",
        PromptRole.POSITIVE,
    )
    assert [(scene.key, scene.title, scene.order) for scene in analysis.scenes] == [
        ("portrait", "portrait", 0),
        ("cafe", "cafe", 1),
    ]
    assert analysis.can_generate_scenes is True


def test_scene_analysis_reports_secondary_orphan_scene() -> None:
    """A secondary prompt scene missing from the authority prompt should be orphaned."""

    workflow = _workflow(
        stack_order=["Text", "Detailer"],
        prompts={
            ("Text", "positive_prompt"): "**portrait\nportrait",
            ("Detailer", "positive_prompt"): "detail\n**hands\nhands",
        },
    )
    endpoints = _endpoints(
        ("Text", PromptRole.POSITIVE, "positive_prompt"),
        ("Detailer", PromptRole.POSITIVE, "positive_prompt"),
    )
    detailer_endpoint = endpoints.endpoint_for("Detailer", PromptRole.POSITIVE)
    assert detailer_endpoint is not None

    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoints,
    )

    assert analysis.diagnostics_by_endpoint[
        detailer_endpoint
    ].orphan_scene_keys == frozenset({"hands"})


def test_scene_analysis_reports_duplicate_authority_scene() -> None:
    """Duplicate authority scene markers should be reported as endpoint diagnostics."""

    workflow = _workflow(
        stack_order=["Text"],
        prompts={
            ("Text", "positive_prompt"): "**portrait\none\n**Portrait\ntwo",
        },
    )
    endpoints = _endpoints(("Text", PromptRole.POSITIVE, "positive_prompt"))
    authority_endpoint = endpoints.endpoint_for("Text", PromptRole.POSITIVE)
    assert authority_endpoint is not None

    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoints,
    )

    assert [(scene.key, scene.order) for scene in analysis.scenes] == [("portrait", 0)]
    assert analysis.diagnostics_by_endpoint[
        authority_endpoint
    ].duplicate_scene_keys == frozenset({"portrait"})


def test_scene_analysis_without_positive_prompt_cannot_generate_scenes() -> None:
    """Scene generation should be unavailable when no positive authority exists."""

    workflow = _workflow(
        stack_order=["Negative"],
        prompts={("Negative", "negative_prompt"): "**portrait\nbad"},
    )
    endpoints = _endpoints(("Negative", PromptRole.NEGATIVE, "negative_prompt"))

    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoints,
    )

    assert analysis.authority_endpoint is None
    assert analysis.scenes == ()
    assert analysis.can_generate_scenes is False


def test_scene_analysis_without_authority_scenes_cannot_generate_scenes() -> None:
    """A positive prompt with only universal text should not enable scene generation."""

    workflow = _workflow(
        stack_order=["Text"],
        prompts={("Text", "positive_prompt"): "quality"},
    )
    endpoints = _endpoints(("Text", PromptRole.POSITIVE, "positive_prompt"))

    analysis = PromptSceneAnalysisService().analyze(
        workflow=workflow,
        endpoint_index=endpoints,
    )

    assert analysis.authority_endpoint is not None
    assert analysis.scenes == ()
    assert analysis.can_generate_scenes is False


def _workflow(
    *,
    stack_order: list[str],
    prompts: dict[tuple[str, str], str],
) -> SimpleNamespace:
    """Build lightweight workflow state with prompt node buffers."""

    cubes: dict[str, SimpleNamespace] = {}
    for cube_alias in stack_order:
        nodes = {
            node_name: {"inputs": {"prompt_template": value}}
            for (prompt_cube, node_name), value in prompts.items()
            if prompt_cube == cube_alias
        }
        cubes[cube_alias] = SimpleNamespace(buffer={"nodes": nodes})
    return SimpleNamespace(stack_order=stack_order, cubes=cubes)


def _endpoints(
    *items: tuple[str, PromptRole, str],
) -> PromptEndpointIndex:
    """Build prompt endpoints for scene analysis tests."""

    return PromptEndpointIndex.from_endpoints(
        PromptEndpoint(
            cube_alias=cube_alias,
            role=role,
            node_name=node_name,
            field_key="prompt_template",
        )
        for cube_alias, role, node_name in items
    )
