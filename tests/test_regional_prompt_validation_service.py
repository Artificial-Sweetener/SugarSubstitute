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

"""Verify topology-owned regional prompt and mask validation."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.regional_prompt_validation_service import (
    RegionalPromptValidationService,
)
from substitute.application.workflows.regional_prompt_topology_service import (
    RegionalPromptTopologyService,
)
from substitute.application.workflows.regional_prompt_label_service import (
    RegionalPromptLabelService,
)
from substitute.domain.workflow import CubeState, ProjectMaskAssetRef, WorkflowState


def _workflow(prompt: str, *, mask_count: int) -> WorkflowState:
    """Build one Prompt by Region topology with an ordered mask collection."""

    workflow = WorkflowState()
    workflow.cubes["Region"] = CubeState(
        cube_id="Prompt by Region.cube",
        version="3.2.0",
        alias="Region",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "masks": {
                    "class_type": "SimpleSyrup.LoadMaskBatch",
                    "inputs": {"image": []},
                },
                "positive": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {"value": prompt},
                },
                "negative": {
                    "class_type": "PrimitiveStringMultiline",
                    "inputs": {"value": "global negative"},
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
                        "negative": ["encode", 2],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Region")
    image_id = uuid4()
    collection = workflow.canvas.ensure_regional_mask_collection(("Region", "masks"))
    for index in range(mask_count):
        collection.add_region(
            image_id,
            mask_id=uuid4(),
            asset_ref=ProjectMaskAssetRef(f"region-{index}.png"),
        )
    return workflow


def test_regional_prompt_validation_blocks_prompt_regions_without_masks() -> None:
    """Each regional prompt partition must have a materialized ordered mask."""

    issues = RegionalPromptValidationService().validate(
        _workflow("global\n[SEP]\nfirst\n[SEP|Second]\nsecond", mask_count=1)
    )

    assert len(issues) == 1
    assert issues[0].association_key == ("Region", "masks")
    assert issues[0].required_region_count == 2
    assert issues[0].available_mask_count == 1


def test_regional_prompt_validation_allows_extra_editable_masks() -> None:
    """Extra masks should remain editable and should not block generation."""

    assert (
        RegionalPromptValidationService().validate(
            _workflow("global\n[SEP]\nfirst", mask_count=3)
        )
        == ()
    )


def test_regional_prompt_topology_resolves_prompt_nodes_to_mask_endpoint() -> None:
    """Positive and negative prompt identity should derive from shared graph topology."""

    workflow = _workflow("global\n[SEP]\nfirst", mask_count=1)
    service = RegionalPromptTopologyService()

    topology = service.topology_for_prompt(workflow, "Region", "positive")

    assert topology is not None
    assert topology.association_key == ("Region", "masks")
    assert topology.prompt_node_names == ("positive", "negative")
    assert service.topology_for_mask(workflow, ("Region", "masks")) == topology


def test_regional_prompt_labels_follow_authored_sep_names_in_mask_order() -> None:
    """Mask labels should prefer the first authored name across related prompts."""

    workflow = _workflow(
        "global\n[SEP|Character]\nfirst\n[SEP]\nsecond",
        mask_count=3,
    )

    labels = RegionalPromptLabelService().labels_for_mask(
        workflow,
        ("Region", "masks"),
        region_count=3,
    )

    assert labels == ("Character", None, None)


def test_regional_prompt_labels_accept_current_editor_text_before_graph_commit() -> (
    None
):
    """Live panel projection should use the changed prompt's current source snapshot."""

    workflow = _workflow("global\n[SEP|Old]\nfirst", mask_count=1)

    labels = RegionalPromptLabelService().labels_for_mask(
        workflow,
        ("Region", "masks"),
        region_count=1,
        prompt_text_overrides={"positive": "global\n[SEP|New]\nfirst"},
    )

    assert labels == ("New",)
