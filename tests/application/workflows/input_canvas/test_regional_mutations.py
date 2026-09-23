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

import pytest

from substitute.application.workflows import (
    WorkflowInputCanvasService,
)
from substitute.application.workflows.input_canvas_ports import (
    MaskLayerRemovalOutcome,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.ordered_mask_materialization_service import (
    OrderedMaskMaterializationService,
)
from substitute.application.workflows.ordered_mask_region_authoring_service import (
    OrderedMaskRegionAuthoringService,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState
from substitute.domain.workflow import WorkflowState
from typing import Any, cast
from uuid import uuid4

from tests.application.workflows.input_canvas.fakes import (
    _FakeImage,
    _FakeSize,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)
from tests.application.workflows.input_canvas.support import (
    _fake_input_state_composition,
    _input_canvas_binding_service,
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
                        "positive": "α [SEP|left] e\u0301moji 🧁\n[SEP|right] שלום",
                        "negative": "  preserve\r\nbytes [SEP|negative]  ",
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
        input_bindings=_input_canvas_binding_service(definitions),
        input_state=_fake_input_state_composition(state_service),
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
    prompt_bytes = _prompt_bytes(workflow)
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
    assert _prompt_bytes(workflow) == prompt_bytes
    assert state_service.activated_masks == [second_mask_id]
    nodes = cast(dict[str, object], workflow.cubes["Region"].buffer["nodes"])
    mask_node = cast(dict[str, object], nodes["masks"])
    inputs = cast(dict[str, object], mask_node["inputs"])
    assert inputs["image"] == ["region.png", "region.png"]


def test_prompt_by_region_imports_normalized_mask_and_removes_exact_region(
    tmp_path: Path,
) -> None:
    """Removal should persist even when the live mask layer is already absent."""

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
                        "positive": "[SEP|first]\nα e\u0301 🧁\n[SEP|second] שלום",
                        "negative": "  [SEP|only negative]\r\nkeep spaces  ",
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
        input_bindings=_input_canvas_binding_service(definitions),
        input_state=_fake_input_state_composition(state_service),
        canvas_io_service=io_service,
    )
    service.materialize_loaded_section(
        workflows={"workflow": workflow},
        workflow_id="workflow",
        section_key="Region",
        workflow_name="Region",
        projects_dir=tmp_path,
    )
    prompt_bytes = _prompt_bytes(workflow)
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
    assert _prompt_bytes(workflow) == prompt_bytes
    state_service.authorize_mask_removal = False
    rejected = service.remove_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key="Region",
        node_name="masks",
        region_index=0,
    )
    collection = workflow.canvas.regional_mask_collection(("Region", "masks"))
    assert collection is not None
    assert rejected is False
    assert _prompt_bytes(workflow) == prompt_bytes
    assert [entry.mask_id for entry in collection.entries] == [
        first_mask_id,
        imported_mask_id,
    ]

    state_service.authorize_mask_removal = True
    state_service.remove_mask_result = MaskLayerRemovalOutcome.ALREADY_ABSENT
    removed = service.remove_ordered_mask_region(
        workflow=workflow,
        workflow_id="workflow",
        section_key="Region",
        node_name="masks",
        region_index=0,
    )

    assert imported == imported_mask_id
    assert removed is True
    assert _prompt_bytes(workflow) == prompt_bytes
    assert [entry.mask_id for entry in collection.entries] == [imported_mask_id]
    assert state_service.updated_masks == [
        (("Region", "masks"), imported_mask_id, expected_mask)
    ]
    assert state_service.removed_masks == [(image_id, first_mask_id)]
    nodes = cast(dict[str, object], workflow.cubes["Region"].buffer["nodes"])
    mask_node = cast(dict[str, object], nodes["masks"])
    inputs = cast(dict[str, object], mask_node["inputs"])
    assert inputs["image"] == ["region.png"]

    failing_authoring = OrderedMaskRegionAuthoringService(
        binding_resolver=_input_canvas_binding_service(definitions).binding_for_mask,
        ensure_section_materialized=lambda *_args: None,
        input_routes=cast(Any, state_service),
        input_images=cast(Any, state_service),
        input_masks=cast(Any, state_service),
        canvas_io_service=io_service,
        materialization_service=cast(OrderedMaskMaterializationService, object()),
        graph_values=cast(OrderedMaskGraphValueService, _FailingGraphValues()),
    )
    with pytest.raises(RuntimeError, match="graph write failed"):
        failing_authoring.remove_region(
            workflow=workflow,
            workflow_id="workflow",
            section_key="Region",
            node_name="masks",
            region_index=0,
        )

    assert [entry.mask_id for entry in collection.entries] == [imported_mask_id]
    assert inputs["image"] == ["region.png"]
    assert state_service.removed_masks == [(image_id, first_mask_id)]


def _prompt_bytes(workflow: WorkflowState) -> tuple[bytes, bytes]:
    """Return exact UTF-8 prompt bytes from the production graph buffer."""

    nodes = cast(dict[str, object], workflow.cubes["Region"].buffer["nodes"])
    sampler = cast(dict[str, object], nodes["sampler"])
    inputs = cast(dict[str, object], sampler["inputs"])
    return (
        cast(str, inputs["positive"]).encode("utf-8"),
        cast(str, inputs["negative"]).encode("utf-8"),
    )


class _FailingGraphValues:
    """Fail one durable mutation and accept the collection rollback."""

    def __init__(self) -> None:
        """Initialize one pending injected failure."""

        self._failed = False

    def synchronize(self, *_args: object) -> bool:
        """Raise once, then accept rollback synchronization."""

        if not self._failed:
            self._failed = True
            raise RuntimeError("graph write failed")
        return True
