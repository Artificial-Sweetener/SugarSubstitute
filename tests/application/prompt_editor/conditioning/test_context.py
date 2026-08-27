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

"""Contract tests for graph-derived prompt conditioning context."""

from __future__ import annotations

from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContextService,
    PromptConditioningMode,
)
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.domain.node_behavior.models import PromptRole
from substitute.domain.workflow import CubeState, WorkflowState


def test_context_resolver_classifies_exact_regional_prompt_endpoint() -> None:
    """Regional classification should require the graph-backed field identity."""

    workflow = _regional_workflow()
    service = PromptConditioningContextService()

    regional = service.resolve(workflow, _endpoint("positive", "value"))
    unrelated_field = service.resolve(workflow, _endpoint("positive", "caption"))

    assert regional.mode is PromptConditioningMode.REGIONAL
    assert unrelated_field.mode is PromptConditioningMode.INDEPENDENT
    assert regional.identity != unrelated_field.identity


def test_context_resolver_distinguishes_multiple_prompt_endpoints_in_cube() -> None:
    """Each prompt endpoint should retain its own role, node, and field identity."""

    workflow = _regional_workflow()
    service = PromptConditioningContextService()

    positive = service.resolve(workflow, _endpoint("positive", "value"))
    negative = service.resolve(
        workflow,
        PromptEndpoint(
            cube_alias="Region",
            role=PromptRole.NEGATIVE,
            node_name="negative",
            field_key="value",
        ),
    )

    assert positive.mode is PromptConditioningMode.REGIONAL
    assert negative.mode is PromptConditioningMode.REGIONAL
    assert positive.identity != negative.identity


def test_context_resolver_marks_missing_workflow_unresolved() -> None:
    """Missing workflow ownership should not assert a regional classification."""

    context = PromptConditioningContextService().resolve(
        None,
        _endpoint("positive", "value"),
    )

    assert context.mode is PromptConditioningMode.UNRESOLVED


def test_context_resolver_detects_ordered_graph_before_mask_materialization() -> None:
    """Regional mode should derive from ordered graph endpoints, not authored mask state."""

    workflow = _regional_workflow(include_mask_collection=False)

    context = PromptConditioningContextService().resolve(
        workflow,
        _endpoint("positive", "value"),
    )

    assert workflow.canvas.regional_mask_collections == {}
    assert context.mode is PromptConditioningMode.REGIONAL


def test_context_identity_changes_when_regional_topology_materializes() -> None:
    """Async consumers should detect ordered-mask topology changes."""

    workflow = _regional_workflow(
        include_mask_collection=False,
        ordered_mask_endpoint=False,
    )
    service = PromptConditioningContextService()
    endpoint = _endpoint("positive", "value")
    before = service.resolve(workflow, endpoint)

    nodes = workflow.cubes["Region"].buffer["nodes"]
    assert isinstance(nodes, dict)
    masks = nodes["masks"]
    assert isinstance(masks, dict)
    masks["class_type"] = "SimpleSyrup.LoadMaskBatch"
    after = service.resolve(workflow, endpoint)

    assert before.mode is PromptConditioningMode.INDEPENDENT
    assert after.mode is PromptConditioningMode.REGIONAL
    assert before.identity != after.identity


def _endpoint(node_name: str, field_key: str) -> PromptEndpoint:
    """Return one positive prompt endpoint in the regional test cube."""

    return PromptEndpoint(
        cube_alias="Region",
        role=PromptRole.POSITIVE,
        node_name=node_name,
        field_key=field_key,
    )


def _regional_workflow(
    *,
    include_mask_collection: bool = True,
    ordered_mask_endpoint: bool = True,
) -> WorkflowState:
    """Build a compact graph with two prompt sources and one ordered mask consumer."""

    workflow = WorkflowState()
    workflow.cubes["Region"] = CubeState(
        cube_id="Prompt by Region.cube",
        version="3.2.0",
        alias="Region",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "masks": {
                    "class_type": (
                        "SimpleSyrup.LoadMaskBatch"
                        if ordered_mask_endpoint
                        else "LoadImageMask"
                    ),
                    "inputs": {"image": []},
                },
                "positive": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {"value": "global\n[SEP]\nregion", "caption": "note"},
                },
                "negative": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {"value": "negative"},
                },
                "encode": {
                    "class_type": "SchedulePrompts",
                    "inputs": {
                        "positive_prompt": ["positive", 0],
                        "negative_prompt": ["negative", 0],
                    },
                },
                "sampler": {
                    "class_type": "RegionalSampler",
                    "inputs": {
                        "region_masks": ["masks", 0],
                        "positive": ["encode", 1],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Region")
    if include_mask_collection:
        workflow.canvas.ensure_regional_mask_collection(("Region", "masks"))
    return workflow
