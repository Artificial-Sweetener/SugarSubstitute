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
from substitute.domain.workflow import CubeState
from uuid import uuid4

from tests.application.workflows.input_canvas.fakes import (
    _FakeImage,
    _FakeInputCanvasStateService,
    _FakeCanvasIoService,
)
from tests.application.workflows.input_canvas.support import (
    _build_workflow,
    _workflow_input_service,
)


def test_unambiguous_bound_image_identity_returns_only_bound_input() -> None:
    """Direct canvas loads can target a workflow with one editable image binding."""

    workflow = _build_workflow("")

    identity = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    ).unambiguous_bound_image_identity(workflow)

    assert identity == ("CubeA", "input_image")


def test_resolve_loaded_input_canvas_image_identity_uses_mapped_input_key() -> None:
    """Direct QPane loads should prefer existing workflow input-key ownership."""

    image_id = uuid4()
    workflow = _build_workflow("")
    workflow.canvas.bind_image("CubeA:input_image", image_id)
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        image_id,
    )

    assert resolution.accepted is True
    assert resolution.cube_alias == "CubeA"
    assert resolution.image_node_name == "input_image"
    assert resolution.input_key == "CubeA:input_image"


def test_resolve_loaded_input_canvas_image_identity_uses_single_bound_input() -> None:
    """Unmapped direct QPane loads should target one unambiguous graph-bound image."""

    workflow = _build_workflow("")
    image_id = uuid4()
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        image_id,
    )

    assert resolution.accepted is True
    assert resolution.input_key == "CubeA:input_image"
    assert workflow.canvas.image_entries == {}


def test_resolve_loaded_input_canvas_image_identity_rejects_malformed_key() -> None:
    """Malformed mapped input keys should fail before graph reconciliation."""

    image_id = uuid4()
    workflow = _build_workflow("")
    workflow.canvas.bind_image("malformed", image_id)
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        image_id,
    )

    assert resolution.accepted is False
    assert resolution.input_key == "malformed"
    assert resolution.rejection_reason == "malformed_input_key"


def test_resolve_loaded_input_canvas_image_identity_rejects_ambiguous_bound_inputs() -> (
    None
):
    """Direct QPane loads should not guess between multiple graph-bound inputs."""

    workflow = _build_workflow("")
    workflow.cubes["CubeB"] = CubeState(
        cube_id="CubeB",
        version="1.0.0",
        alias="CubeB",
        original_cube={"nodes": {}},
        buffer={
            "nodes": {
                "image": {"class_type": "LoadImage", "inputs": {"image": ""}},
                "mask": {"class_type": "LoadImageMask", "inputs": {"image": ""}},
                "consumer": {
                    "class_type": "Blend",
                    "inputs": {"image": ["image", 0], "mask": ["mask", 0]},
                },
            }
        },
    )
    workflow.stack_order.append("CubeB")
    service = _workflow_input_service(
        _FakeInputCanvasStateService(image_id=uuid4(), mask_id=uuid4()),
        _FakeCanvasIoService(
            image=_FakeImage(),
            expected_mask_path=Path("E:/masks/mask.png"),
            created_destinations=[],
        ),
    )

    resolution = service.resolve_loaded_input_canvas_image_identity(
        workflow,
        uuid4(),
    )

    assert resolution.accepted is False
    assert resolution.rejection_reason == "unmapped_image_id"
