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


def test_materialize_loaded_section_creates_synthetic_mask_only_canvas(
    tmp_path: Path,
) -> None:
    """A resolved spatial root should create one backing image and mask layer."""

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
                    "inputs": {"image": "mask.png"},
                },
                "region": {
                    "class_type": "PackRegionalCondition",
                    "inputs": {"mask": ["mask", 0]},
                },
                "noise": {
                    "class_type": "PackNoiseLatent",
                    "inputs": {"width": 896, "height": 1152},
                },
                "sampler": {
                    "class_type": "PackSampler",
                    "inputs": {
                        "latent": ["noise", 0],
                        "conditioning": ["region", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Regional")
    definitions: dict[str, JsonObject] = {
        "LoadImageMask": {
            "input": {
                "required": {
                    "image": [
                        "STRING",
                        {"image_upload": True, "image_folder": "input"},
                    ]
                }
            },
            "output": ["MASK"],
        },
        "PackRegionalCondition": {
            "input": {"required": {"mask": ["MASK", {}]}},
            "output": ["CONDITIONING"],
        },
        "PackNoiseLatent": {
            "input": {
                "required": {
                    "width": ["INT", {}],
                    "height": ["INT", {}],
                }
            },
            "output": ["LATENT"],
        },
        "PackSampler": {
            "input": {
                "required": {
                    "latent": ["LATENT", {}],
                    "conditioning": ["CONDITIONING", {}],
                }
            },
            "output": ["LATENT"],
        },
    }
    image_id = uuid4()
    mask_id = uuid4()
    expected_mask = tmp_path / "Regional Recipe" / "masks" / "regional.png"
    state_service = _FakeInputCanvasStateService(
        image_id=image_id,
        mask_id=mask_id,
    )
    io_service = _FakeCanvasIoService(
        image=_FakeImage(size_value=_FakeSize(896, 1152)),
        expected_mask_path=expected_mask,
        dimensions_by_path={},
        created_destinations=[],
    )
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(definitions),
        input_canvas_state_service=state_service,
        canvas_io_service=io_service,
    )

    results = service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key="Regional",
        workflow_name="Regional Recipe",
        projects_dir=tmp_path,
    )

    assert len(results) == 1
    assert results[0].image_id == image_id
    assert workflow.canvas.image_ids() == (image_id,)
    synthetic_key = next(iter(workflow.canvas.image_entries))
    assert synthetic_key.startswith("Regional:@synthetic/")
    mask_entry = workflow.canvas.mask_entry(("Regional", "mask"))
    assert mask_entry is not None
    assert mask_entry.mask_id == mask_id
    assert mask_entry.image_id == image_id


def test_prompt_by_region_materializes_initial_ordered_mask_at_latent_size(
    tmp_path: Path,
) -> None:
    """Prompt by Region should open with one blank ordered region on its canvas."""

    workflow = WorkflowState()
    workflow.cubes["Prompt by Region"] = CubeState(
        cube_id="Artificial-Sweetener/Base-Cubes/Anima/Prompt by Region.cube",
        version="3.2.0",
        alias="Prompt by Region",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "load_mask_batch": {
                    "class_type": "SimpleSyrup.LoadMaskBatch",
                    "inputs": {"image": [], "channel": "alpha"},
                },
                "latent_dimensions": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": 960, "height": 1344, "batch_size": 1},
                },
                "ksampler": {
                    "class_type": "SimpleSyrup.KSamplerPromptByRegion",
                    "inputs": {
                        "region_masks": ["load_mask_batch", 0],
                        "latent_image": ["latent_dimensions", 0],
                    },
                },
            }
        },
    )
    workflow.stack_order.append("Prompt by Region")
    definitions: dict[str, JsonObject] = {
        "SimpleSyrup.LoadMaskBatch": {
            "input": {
                "required": {
                    "image": [
                        "LIST",
                        {
                            "image_upload": True,
                            "image_folder": "input",
                            "allow_batch": True,
                        },
                    ],
                    "channel": ["LIST"],
                }
            },
            "output": ["MASK"],
        },
        "EmptyLatentImage": {
            "input": {
                "required": {
                    "width": ["INT", {}],
                    "height": ["INT", {}],
                    "batch_size": ["INT", {}],
                }
            },
            "output": ["LATENT"],
        },
        "SimpleSyrup.KSamplerPromptByRegion": {
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
    mask_id = uuid4()
    expected_mask = tmp_path / "Regional Recipe" / "masks" / "region.png"
    state_service = _FakeInputCanvasStateService(
        image_id=image_id,
        mask_id=mask_id,
    )
    created_destinations: list[Path] = []
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(definitions),
        input_canvas_state_service=state_service,
        canvas_io_service=_FakeCanvasIoService(
            image=_FakeImage(size_value=_FakeSize(960, 1344)),
            expected_mask_path=expected_mask,
            created_destinations=created_destinations,
        ),
    )

    results = service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key="Prompt by Region",
        workflow_name="Regional Recipe",
        projects_dir=tmp_path,
    )

    assert len(results) == 1
    assert len(results[0].mask_results) == 1
    collection = workflow.canvas.regional_mask_collection(
        ("Prompt by Region", "load_mask_batch")
    )
    assert collection is not None
    assert len(collection.entries) == 1
    assert collection.entries[0].mask_id == mask_id
    assert collection.selected_region_id == collection.entries[0].region_id
    assert created_destinations == [expected_mask]
    cube = workflow.cubes["Prompt by Region"]
    nodes = cast(dict[str, object], cube.buffer["nodes"])
    mask_node = cast(dict[str, object], nodes["load_mask_batch"])
    inputs = cast(dict[str, object], mask_node["inputs"])
    assert inputs["image"] == ["region.png"]


def test_prompt_by_region_first_add_materializes_synthetic_surface(
    tmp_path: Path,
) -> None:
    """The first Add gesture should create the canvas and one region atomically."""

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
                    "inputs": {"channel": "alpha"},
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
    mask_id = uuid4()
    expected_mask = tmp_path / "Recipe" / "masks" / "region.png"
    state_service = _FakeInputCanvasStateService(image_id=image_id, mask_id=mask_id)
    service = WorkflowInputCanvasService(
        input_canvas_plan_service=_input_canvas_plan_service(definitions),
        input_canvas_state_service=state_service,
        canvas_io_service=_FakeCanvasIoService(
            image=_FakeImage(size_value=_FakeSize(960, 1344)),
            expected_mask_path=expected_mask,
            created_destinations=[],
        ),
    )

    created = service.add_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key="Region",
        node_name="masks",
        workflow_name="Recipe",
        projects_dir=tmp_path,
    )

    assert created == mask_id
    collection = workflow.canvas.regional_mask_collection(("Region", "masks"))
    assert collection is not None
    assert len(collection.entries) == 1
    assert collection.entries[0].mask_id == mask_id
    created_size = cast(_FakeSize, state_service.created_masks[0][1])
    assert created_size.width() == 960
    assert created_size.height() == 1344
