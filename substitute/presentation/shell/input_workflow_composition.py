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

"""Compose graph-backed Input workflow application owners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from substitute.application.workflows.input_canvas_binding_service import (
    InputCanvasBindingService,
)
from substitute.application.workflows.ordered_mask_graph_value_service import (
    OrderedMaskGraphValueService,
)
from substitute.application.workflows.restored_ordered_mask_collection_service import (
    RestoredOrderedMaskCollectionService,
)
from substitute.application.workflows.workflow_input_canvas_duplication_service import (
    WorkflowInputCanvasDuplicationService,
)
from substitute.application.workflows.workflow_input_canvas_service import (
    WorkflowInputCanvasService,
)


@dataclass(frozen=True)
class InputWorkflowComposition:
    """Hold graph-backed Input workflow owners."""

    bindings: InputCanvasBindingService
    workflows: WorkflowInputCanvasService
    duplication: WorkflowInputCanvasDuplicationService
    restored_masks: RestoredOrderedMaskCollectionService


def compose_input_workflow_services(
    *,
    shell: Any,
    input_document: Any,
) -> InputWorkflowComposition:
    """Compose Input binding, materialization, duplication, and restore owners."""

    bindings = InputCanvasBindingService(
        plans=shell.input_canvas_plan_service,
        graph_sections=shell.graph_section_service,
    )
    workflows = WorkflowInputCanvasService(
        input_bindings=bindings,
        input_state=shell.input_canvas_state,
        canvas_io_service=shell.canvas_io_service,
        workflow_asset_service=shell.workflow_asset_service,
        graph_section_service=shell.graph_section_service,
    )
    duplication = WorkflowInputCanvasDuplicationService(
        input_bindings=bindings,
        graph_sections=shell.graph_section_service,
        input_document=input_document,
        canvas_io=shell.canvas_io_service,
    )
    restored_masks = RestoredOrderedMaskCollectionService(
        endpoint_service=shell.input_asset_endpoint_service,
        graph_sections=shell.graph_section_service,
        graph_values=OrderedMaskGraphValueService(shell.graph_section_service),
    )
    return InputWorkflowComposition(
        bindings=bindings,
        workflows=workflows,
        duplication=duplication,
        restored_masks=restored_masks,
    )


__all__ = ["InputWorkflowComposition", "compose_input_workflow_services"]
