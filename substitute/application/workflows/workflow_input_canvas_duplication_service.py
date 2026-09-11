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

"""Prepare independent Input-canvas assets for workflow duplication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_canvas_ports import CanvasIoServicePort
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.application.workflows.workflow_input_canvas_service import (
    WorkflowInputCanvasService,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("application.workflows.workflow_input_canvas_duplication_service")


@dataclass(frozen=True, slots=True)
class DuplicatedRegionalMaskPresentation:
    """Retain ordered colors and selection while live mask IDs are replaced."""

    association_key: tuple[str, str]
    authored_colors: tuple[str | None, ...]
    selected_index: int | None


@dataclass(frozen=True, slots=True)
class WorkflowInputCanvasDuplicationPlan:
    """Describe presentation state to apply after target asset rehydration."""

    regional_presentations: tuple[DuplicatedRegionalMaskPresentation, ...]
    copied_mask_count: int


class WorkflowInputCanvasDuplicationService:
    """Copy current editable masks into a duplicate's independent graph assets."""

    def __init__(
        self,
        *,
        workflow_inputs: WorkflowInputCanvasService,
        graph_sections: WorkflowGraphSectionService,
        input_document: InputCanvasDocumentPort,
        canvas_io: CanvasIoServicePort,
    ) -> None:
        """Capture graph, document, and filesystem authorities."""

        self._workflow_inputs = workflow_inputs
        self._graph_sections = graph_sections
        self._input_document = input_document
        self._canvas_io = canvas_io

    def prepare(
        self,
        *,
        source: WorkflowState,
        target: WorkflowState,
        target_workflow_name: str,
        projects_dir: Path,
    ) -> WorkflowInputCanvasDuplicationPlan:
        """Persist live source mask pixels and point the target graph at copies."""

        presentations: list[DuplicatedRegionalMaskPresentation] = []
        copied_count = 0
        regional_keys = set(source.canvas.regional_mask_collections)
        for (
            association_key,
            collection,
        ) in source.canvas.regional_mask_collections.items():
            section_key, node_name = association_key
            binding = self._workflow_inputs.binding_for_mask(
                source,
                section_key,
                node_name,
            )
            if binding is None:
                continue
            target_paths: list[str] = []
            for entry in collection.entries:
                path = self._copy_mask(
                    mask_id=entry.mask_id,
                    image_id=entry.image_id,
                    target_workflow_name=target_workflow_name,
                    section_key=section_key,
                    node_name=f"{node_name}-{entry.region_id.hex}",
                    projects_dir=projects_dir,
                )
                if path is None:
                    raise RuntimeError(
                        "Workflow duplicate could not snapshot an editable regional mask."
                    )
                target_paths.append(path.name)
                copied_count += 1
            self._graph_sections.set_input_value(
                target,
                section_key=section_key,
                node_name=node_name,
                field_key=binding.mask_field_key,
                value=target_paths,
            )
            selected_index = next(
                (
                    index
                    for index, entry in enumerate(collection.entries)
                    if entry.region_id == collection.selected_region_id
                ),
                None,
            )
            presentations.append(
                DuplicatedRegionalMaskPresentation(
                    association_key=association_key,
                    authored_colors=tuple(
                        entry.authored_color for entry in collection.entries
                    ),
                    selected_index=selected_index,
                )
            )

        for association_key, mask_entry in source.canvas.mask_entries.items():
            if association_key in regional_keys:
                continue
            section_key, node_name = association_key
            binding = self._workflow_inputs.binding_for_mask(
                source,
                section_key,
                node_name,
            )
            if binding is None:
                continue
            path = self._copy_mask(
                mask_id=mask_entry.mask_id,
                image_id=mask_entry.image_id,
                target_workflow_name=target_workflow_name,
                section_key=section_key,
                node_name=node_name,
                projects_dir=projects_dir,
            )
            if path is None:
                raise RuntimeError(
                    "Workflow duplicate could not snapshot an editable input mask."
                )
            self._graph_sections.set_input_value(
                target,
                section_key=section_key,
                node_name=node_name,
                field_key=binding.mask_field_key,
                value=path.name,
            )
            copied_count += 1

        plan = WorkflowInputCanvasDuplicationPlan(
            regional_presentations=tuple(presentations),
            copied_mask_count=copied_count,
        )
        log_info(
            _LOGGER,
            "Prepared independent Input assets for workflow duplicate",
            copied_mask_count=copied_count,
            regional_collection_count=len(presentations),
            target_workflow_name=target_workflow_name,
        )
        return plan

    def apply_presentation(
        self,
        target: WorkflowState,
        plan: WorkflowInputCanvasDuplicationPlan,
    ) -> None:
        """Restore ordered region colors and selection after live rehydration."""

        for presentation in plan.regional_presentations:
            collection = target.canvas.regional_mask_collection(
                presentation.association_key
            )
            if collection is None or len(collection.entries) != len(
                presentation.authored_colors
            ):
                raise RuntimeError(
                    "Workflow duplicate rehydrated an unexpected regional mask count."
                )
            for entry, authored_color in zip(
                collection.entries,
                presentation.authored_colors,
                strict=True,
            ):
                collection.set_authored_color(entry.region_id, authored_color)
            if presentation.selected_index is not None:
                collection.select(
                    collection.entries[presentation.selected_index].region_id
                )

    def _copy_mask(
        self,
        *,
        mask_id: object,
        image_id: object,
        target_workflow_name: str,
        section_key: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Persist one exact live mask into a collision-safe target artifact."""

        from uuid import UUID

        if not isinstance(mask_id, UUID) or not isinstance(image_id, UUID):
            return None
        image = self._input_document.export_mask_image(mask_id)
        if image is None:
            return None
        image_path = self._input_document.image_path(image_id) or Path(
            f"{section_key}-{node_name}-input.png"
        )
        dimensions = _image_dimensions(image)
        destination = self._canvas_io.allocate_bound_mask_path(
            workflow_name=target_workflow_name,
            associated_image_path=image_path,
            cube_alias=section_key,
            mask_node_name=node_name,
            image_size=dimensions,
            projects_dir=projects_dir,
        )
        if not self._canvas_io.save_mask_image(destination=destination, image=image):
            return None
        return destination


def _image_dimensions(image: object) -> tuple[int, int] | None:
    """Return positive dimensions from a Qt-like image payload."""

    width = getattr(image, "width", None)
    height = getattr(image, "height", None)
    if not callable(width) or not callable(height):
        return None
    resolved = (int(width()), int(height()))
    return resolved if resolved[0] > 0 and resolved[1] > 0 else None


__all__ = [
    "WorkflowInputCanvasDuplicationPlan",
    "WorkflowInputCanvasDuplicationService",
]
