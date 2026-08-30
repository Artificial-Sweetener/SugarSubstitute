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

"""Build deterministic input generation snapshot scenarios."""

from pathlib import Path
from typing import cast
from uuid import UUID

from PySide6.QtGui import QColor, QImage

from substitute.domain.workflow import CubeState, WorkflowState


class _Io:
    """Persist detached products into deterministic project namespaces."""

    def __init__(self, root: Path, *, fail_images: bool = False) -> None:
        """Store product root and failure policy."""
        self._root = root
        self._fail_images = fail_images
        self.saved: list[tuple[Path, QImage]] = []

    def resolve_input_image_save_path(
        self,
        *,
        workflow_name: str,
        image_filename: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve one image product path."""
        assert projects_dir == self._root
        return projects_dir / workflow_name / "input_images" / Path(image_filename)

    def save_input_image(self, *, destination: Path, image: object) -> bool:
        """Persist or reject one exact image product."""
        assert isinstance(image, QImage)
        if self._fail_images:
            return False
        self.saved.append((destination, image.copy()))
        return True

    def resolve_mask_save_path(
        self,
        *,
        workflow_name: str,
        mask_filename: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve one mask product path."""
        assert projects_dir == self._root
        return projects_dir / workflow_name / "masks" / Path(mask_filename)

    def save_mask_image(self, *, destination: Path, image: object) -> bool:
        """Persist one exact mask product."""
        assert isinstance(image, QImage)
        self.saved.append((destination, image.copy()))
        return True


class _Associations:
    """Associate product paths only in the execution workflow copy."""

    def associate_project_input_image(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Replace one copied image input."""
        self._set(workflow, section_key, node_name, relative_path)
        return True

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Replace one copied mask input."""
        self._set(workflow, section_key, node_name, relative_path)
        return True

    def associate_project_ordered_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        region_id: UUID,
        relative_path: Path | str,
    ) -> bool:
        """Accept ordered association through the same execution-copy fake."""

        _ = region_id
        self._set(workflow, section_key, node_name, relative_path)
        return True

    @staticmethod
    def _set(
        workflow: WorkflowState,
        section_key: str,
        node_name: str,
        relative_path: Path | str,
    ) -> None:
        """Apply one project-relative product value."""
        _nodes(workflow, section_key)[node_name]["inputs"]["image"] = Path(
            relative_path
        ).as_posix()


def _workflow(image_id: UUID, mask_id: UUID) -> WorkflowState:
    """Return one graph with authored image and mask endpoints."""
    cube = CubeState(
        cube_id="cube-a",
        version="1",
        alias="CubeA",
        original_cube={},
        buffer={
            "nodes": {
                "ImageNode": {
                    "class_type": "LoadImage",
                    "inputs": {"image": "authoring-image.png"},
                },
                "MaskNode": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": "authoring-mask.png"},
                },
            }
        },
    )
    workflow = WorkflowState(cubes={"CubeA": cube}, stack_order=["CubeA"])
    workflow.canvas.bind_image("CubeA:ImageNode", image_id)
    workflow.canvas.bind_mask(("CubeA", "MaskNode"), mask_id, image_id)
    return workflow


def _synthetic_workflow(image_id: UUID, mask_id: UUID) -> WorkflowState:
    """Return one mask-only graph backed by latent dimensions."""

    cube = CubeState(
        cube_id="regional.cube",
        version="1",
        alias="Region",
        original_cube={},
        buffer={
            "nodes": {
                "MaskNode": {
                    "class_type": "LoadImageMask",
                    "inputs": {"image": "authoring-mask.png"},
                },
                "Latent": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"width": 960, "height": 1344, "batch_size": 1},
                },
                "Sampler": {
                    "class_type": "Sampler",
                    "inputs": {
                        "region_masks": ["MaskNode", 0],
                        "latent_image": ["Latent", 0],
                    },
                },
            }
        },
    )
    workflow = WorkflowState(cubes={"Region": cube}, stack_order=["Region"])
    workflow.canvas.bind_image("Region:@synthetic/surface", image_id)
    workflow.canvas.bind_mask(("Region", "MaskNode"), mask_id, image_id)
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


def _image(color: QColor) -> QImage:
    """Return one opaque image product."""
    image = QImage(8, 8, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    return image


def _mask(value: int) -> QImage:
    """Return one grayscale mask product."""
    image = QImage(8, 8, QImage.Format.Format_Grayscale8)
    image.fill(value)
    return image
