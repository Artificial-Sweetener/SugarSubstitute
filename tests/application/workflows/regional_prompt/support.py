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

"""Build regional prompt workflow state shared by focused service tests."""

from __future__ import annotations

from uuid import uuid4

from substitute.domain.workflow import CubeState, ProjectMaskAssetRef, WorkflowState


def build_workflow(prompt: str, *, mask_count: int) -> WorkflowState:
    """Build one Prompt by Region topology with ordered mask assets."""

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
