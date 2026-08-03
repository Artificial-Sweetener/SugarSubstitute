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

"""Prove exact-revision Input mask capture at the generation boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from cutecanvas import MaskExportSnapshot
from PySide6.QtGui import QColor, QImage

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.presentation.canvas.input.input_generation_mask_materializer import (
    InputGenerationMaskMaterializer,
)


def test_generation_snapshot_is_execution_only_and_revision_addressed(
    tmp_path: Path,
) -> None:
    """Generation must not mutate authoring state or reuse a mutable filename."""
    mask_id = uuid4()
    composition_id = uuid4()
    workflow = _workflow(mask_id)
    captured_image = _mask_image(0)
    persisted: list[tuple[Path, QImage]] = []

    def save_mask_image(*, destination: Path, image: object) -> bool:
        """Retain a detached record of the durable generation input."""
        assert isinstance(image, QImage)
        persisted.append((destination, image.copy()))
        return True

    snapshot = MaskExportSnapshot(
        mask_id=mask_id,
        composition_id=composition_id,
        revision=17,
        image=captured_image,
    )
    service = InputGenerationMaskMaterializer(
        canvas_io_service=_Io(tmp_path, save_mask_image),
        workflow_input_canvas_service=_Associations(),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    prepared = service.prepare_workflow(
        workflow_id="wf-a",
        workflow=workflow,
        snapshots={mask_id: snapshot},
    )
    assert isinstance(prepared, WorkflowState)
    captured_image.fill(QColor("white"))

    original_value = _nodes(workflow)["MaskNode"]["inputs"]["image"]
    execution_value = _nodes(prepared)["MaskNode"]["inputs"]["image"]
    expected_relative = f".generation/{mask_id}/17.png"
    assert original_value == "authoring-mask.png"
    assert execution_value == expected_relative
    assert persisted[0][0] == tmp_path / "Recipe" / "masks" / Path(expected_relative)
    assert persisted[0][1].pixelColor(0, 0) == QColor("black")


def test_generation_snapshot_fails_closed_on_write_or_stale_identity(
    tmp_path: Path,
) -> None:
    """No workflow may escape when capture identity or persistence is invalid."""
    mask_id = uuid4()
    workflow = _workflow(mask_id)
    wrong_identity = MaskExportSnapshot(
        mask_id=uuid4(),
        composition_id=uuid4(),
        revision=1,
        image=_mask_image(255),
    )
    failed_capture = InputGenerationMaskMaterializer(
        canvas_io_service=_Io(tmp_path, lambda **_kwargs: True),
        workflow_input_canvas_service=_Associations(),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )
    failed_write = InputGenerationMaskMaterializer(
        canvas_io_service=_Io(tmp_path, lambda **_kwargs: False),
        workflow_input_canvas_service=_Associations(),
        workflow_name_provider=lambda _workflow_id: "Recipe",
        projects_dir_provider=lambda: tmp_path,
    )

    assert (
        failed_capture.prepare_workflow(
            workflow_id="wf-a",
            workflow=workflow,
            snapshots={mask_id: wrong_identity},
        )
        is None
    )
    valid_snapshot = MaskExportSnapshot(
        mask_id=mask_id,
        composition_id=uuid4(),
        revision=2,
        image=_mask_image(255),
    )
    assert (
        failed_write.prepare_workflow(
            workflow_id="wf-a",
            workflow=workflow,
            snapshots={mask_id: valid_snapshot},
        )
        is None
    )
    assert _nodes(workflow)["MaskNode"]["inputs"]["image"] == "authoring-mask.png"


class _Io:
    """Provide deterministic project path resolution and persistence."""

    def __init__(
        self,
        root: Path,
        save: Callable[..., object],
    ) -> None:
        """Store the project root and save callback."""
        self._root = root
        self._save = save

    def resolve_mask_save_path(
        self,
        *,
        workflow_name: str,
        mask_filename: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve the same project mask layout as production."""
        assert projects_dir == self._root
        return projects_dir / workflow_name / "masks" / Path(mask_filename)

    def save_mask_image(self, *, destination: Path, image: object) -> bool:
        """Delegate persistence to the scenario callback."""
        return bool(self._save(destination=destination, image=image))


class _Associations:
    """Mutate only the execution workflow copy passed by the service."""

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Replace one copied graph input with a project-relative snapshot."""
        _nodes(workflow, section_key)[node_name]["inputs"]["image"] = Path(
            relative_path
        ).as_posix()
        return True


def _workflow(mask_id: UUID) -> WorkflowState:
    """Return one real workflow with valid image-to-mask ownership."""
    image_id = uuid4()
    cube = CubeState(
        cube_id="cube-a",
        version="1",
        alias="CubeA",
        original_cube={},
        buffer={
            "nodes": {
                "MaskNode": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": "authoring-mask.png"},
                }
            }
        },
    )
    workflow = WorkflowState(cubes={"CubeA": cube}, stack_order=["CubeA"])
    workflow.canvas.bind_image("CubeA:ImageNode", image_id)
    workflow.canvas.bind_mask(("CubeA", "MaskNode"), mask_id, image_id)
    return workflow


def _nodes(
    workflow: WorkflowState,
    section_key: str = "CubeA",
) -> dict[str, dict[str, dict[str, object]]]:
    """Return the test graph's typed mutable node mapping."""

    return cast(
        "dict[str, dict[str, dict[str, object]]]",
        workflow.cubes[section_key].buffer["nodes"],
    )


def _mask_image(value: int) -> QImage:
    """Return a small grayscale mask filled with one value."""
    image = QImage(4, 4, QImage.Format.Format_Grayscale8)
    image.fill(value)
    return image
