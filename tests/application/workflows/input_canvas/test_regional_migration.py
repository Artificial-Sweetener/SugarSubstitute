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


def test_prompt_by_region_migrates_legacy_scalar_mask_into_ordered_collection(
    tmp_path: Path,
) -> None:
    """A restored one-mask batch should retain its layer identity during migration."""

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
                    "inputs": {"image": "legacy.png", "channel": "alpha"},
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
    legacy_mask_id = uuid4()
    workflow.canvas.bind_mask(("Region", "masks"), legacy_mask_id, image_id)
    state_service = _FakeInputCanvasStateService(
        image_id=image_id,
        mask_id=uuid4(),
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(definitions),
        input_canvas_state_service=state_service,
        canvas_io_service=_FakeCanvasIoService(
            image=_FakeImage(size_value=_FakeSize(960, 1344)),
            expected_mask_path=tmp_path / "Recipe" / "masks" / "legacy.png",
            created_destinations=[],
        ),
    )

    service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key="Region",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    collection = workflow.canvas.regional_mask_collection(("Region", "masks"))
    assert collection is not None
    assert [entry.mask_id for entry in collection.entries] == [legacy_mask_id]
    assert workflow.canvas.mask_entry(("Region", "masks")) is None


def test_synthetic_canvas_authority_change_invalidates_old_surface(
    tmp_path: Path,
) -> None:
    """Dimension fingerprints should retire stale images and mask associations."""

    workflow = WorkflowState()
    workflow.cubes["Regional"] = CubeState(
        cube_id="Regional",
        version="1.0.0",
        alias="Regional",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "mask": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": "old-mask.png"},
                },
                "region": {
                    "class_type": "Regional",
                    "inputs": {"mask": ["mask", 0]},
                },
                "root": {
                    "class_type": "LatentFactory",
                    "inputs": {"width": 768, "height": 1024},
                },
                "sampler": {
                    "class_type": "Sampler",
                    "inputs": {
                        "latent": ["root", 0],
                        "conditioning": ["region", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Regional")
    old_image_id = uuid4()
    old_mask_id = uuid4()
    old_key = "Regional:@synthetic/obsolete"
    workflow.canvas.bind_image(old_key, old_image_id)
    workflow.canvas.bind_mask(("Regional", "mask"), old_mask_id, old_image_id)
    definitions: dict[str, JsonObject] = {
        "LoadImageMask": {
            "input": {"required": {"image": ["STRING", {"image_upload": True}]}},
            "output": ["MASK"],
        },
        "Regional": {
            "input": {"required": {"mask": ["MASK", {}]}},
            "output": ["CONDITIONING"],
        },
        "LatentFactory": {
            "input": {
                "required": {
                    "width": ["INT", {}],
                    "height": ["INT", {}],
                }
            },
            "output": ["LATENT"],
        },
        "Sampler": {
            "input": {
                "required": {
                    "latent": ["LATENT", {}],
                    "conditioning": ["CONDITIONING", {}],
                }
            },
            "output": ["LATENT"],
        },
    }
    new_image_id = uuid4()
    new_mask_id = uuid4()
    state_service = _FakeInputCanvasStateService(
        image_id=new_image_id,
        mask_id=new_mask_id,
    )
    io_service = _FakeCanvasIoService(
        image=_FakeImage(size_value=_FakeSize(768, 1024)),
        expected_mask_path=tmp_path / "Recipe" / "masks" / "new.png",
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
        section_key="Regional",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert workflow.canvas.image_entry(old_key) is None
    assert workflow.canvas.mask_entry_for_id(old_mask_id) is None
    mask_entry = workflow.canvas.mask_entry(("Regional", "mask"))
    assert mask_entry is not None
    assert mask_entry.mask_id == new_mask_id
    assert workflow.canvas.image_ids() == (new_image_id,)
