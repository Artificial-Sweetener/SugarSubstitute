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

"""Verify workflow Input-canvas capability behavior."""

from __future__ import annotations

from pathlib import Path
from substitute.application.workflows import (
    WorkflowInputCanvasService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState
from substitute.domain.workflow import WorkflowState
from typing import cast
from uuid import uuid4

from tests.application.workflows.input_canvas.fakes import (
    _FakeImage,
    _FakeSize,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)
from tests.application.workflows.input_canvas.support import (
    _input_canvas_plan_service,
)


def test_prompt_by_region_can_append_and_activate_another_blank_region(
    tmp_path: Path,
) -> None:
    """The ordered authoring service should create arbitrary additional masks."""

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
                    "inputs": {"image": [], "channel": "alpha"},
                },
                "latent": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": 960, "height": 1344},
                },
                "sampler": {
                    "class_type": "RegionalSampler",
                    "inputs": {
                        "region_masks": ["masks", 0],
                        "latent_image": ["latent", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Region")
    definitions: dict[str, JsonObject] = {
        "SimpleSyrup.LoadMaskBatch": {
            "input": {"required": {"image": ["LIST"], "channel": ["LIST"]}},
            "output": ["MASK"],
        },
        "EmptyLatentImage": {
            "input": {"required": {"width": ["INT", {}], "height": ["INT", {}]}},
            "output": ["LATENT"],
        },
        "RegionalSampler": {
            "input": {
                "required": {
                    "region_masks": ["MASK", {}],
                    "latent_image": ["LATENT", {}],
                }
            },
            "output": ["LATENT"],
        },
    }
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    state_service = _FakeInputCanvasStateService(
        image_id=uuid4(),
        mask_id=first_mask_id,
    )
    expected_mask = tmp_path / "Region" / "masks" / "region.png"
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(definitions),
        input_canvas_state_service=state_service,
        canvas_io_service=_FakeCanvasIoService(
            image=_FakeImage(size_value=_FakeSize(960, 1344)),
            expected_mask_path=expected_mask,
            created_destinations=[],
        ),
    )
    service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key="Region",
        workflow_name="Region",
        projects_dir=tmp_path,
    )
    state_service._mask_id = second_mask_id

    added_mask_id = service.add_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key="Region",
        node_name="masks",
        workflow_name="Region",
        projects_dir=tmp_path,
    )

    collection = workflow.canvas.regional_mask_collection(("Region", "masks"))
    assert collection is not None
    assert [entry.mask_id for entry in collection.entries] == [
        first_mask_id,
        second_mask_id,
    ]
    assert added_mask_id == second_mask_id
    assert state_service.activated_masks == [second_mask_id]
    nodes = cast(dict[str, object], workflow.cubes["Region"].buffer["nodes"])
    mask_node = cast(dict[str, object], nodes["masks"])
    inputs = cast(dict[str, object], mask_node["inputs"])
    assert inputs["image"] == ["region.png", "region.png"]


def test_prompt_by_region_imports_normalized_mask_and_removes_exact_region(
    tmp_path: Path,
) -> None:
    """Imported masks should match latent size and removal should rewrite batch order."""

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
                    "inputs": {"image": [], "channel": "alpha"},
                },
                "latent": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": 960, "height": 1344},
                },
                "sampler": {
                    "class_type": "RegionalSampler",
                    "inputs": {
                        "region_masks": ["masks", 0],
                        "latent_image": ["latent", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Region")
    definitions: dict[str, JsonObject] = {
        "SimpleSyrup.LoadMaskBatch": {
            "input": {"required": {"image": ["LIST"], "channel": ["LIST"]}},
            "output": ["MASK"],
        },
        "EmptyLatentImage": {
            "input": {"required": {"width": ["INT", {}], "height": ["INT", {}]}},
            "output": ["LATENT"],
        },
        "RegionalSampler": {
            "input": {
                "required": {
                    "region_masks": ["MASK", {}],
                    "latent_image": ["LATENT", {}],
                }
            },
            "output": ["LATENT"],
        },
    }
    image_id = uuid4()
    first_mask_id = uuid4()
    imported_mask_id = uuid4()
    state_service = _FakeInputCanvasStateService(
        image_id=image_id,
        mask_id=first_mask_id,
    )
    expected_mask = tmp_path / "Region" / "masks" / "region.png"
    io_service = _FakeCanvasIoService(
        image=_FakeImage(size_value=_FakeSize(960, 1344)),
        expected_mask_path=expected_mask,
        dimensions_by_path={Path("synthetic.png"): (960, 1344)},
        created_destinations=[],
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(definitions),
        input_canvas_state_service=state_service,
        canvas_io_service=io_service,
    )
    service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key="Region",
        workflow_name="Region",
        projects_dir=tmp_path,
    )
    source_path = tmp_path / "authored-mask.png"
    source_path.write_bytes(b"source")
    state_service._mask_id = imported_mask_id

    imported = service.import_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key="Region",
        node_name="masks",
        source_path=source_path,
        workflow_name="Region",
        projects_dir=tmp_path,
    )
    removed = service.remove_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key="Region",
        node_name="masks",
        region_index=0,
    )

    collection = workflow.canvas.regional_mask_collection(("Region", "masks"))
    assert collection is not None
    assert imported == imported_mask_id
    assert removed is True
    assert [entry.mask_id for entry in collection.entries] == [imported_mask_id]
    assert state_service.updated_masks == [
        (("Region", "masks"), imported_mask_id, expected_mask)
    ]
    assert state_service.removed_masks == [(image_id, first_mask_id)]
    nodes = cast(dict[str, object], workflow.cubes["Region"].buffer["nodes"])
    mask_node = cast(dict[str, object], nodes["masks"])
    inputs = cast(dict[str, object], mask_node["inputs"])
    assert inputs["image"] == ["region.png"]
