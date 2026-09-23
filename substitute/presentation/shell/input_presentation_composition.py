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

"""Compose direct Input image, mask, and picker presentation owners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from substitute.application.workflows.workflow_input_canvas_service import (
    WorkflowInputCanvasService,
)
from substitute.presentation.canvas.input.input_image_materialization_presenter import (
    InputImageMaterializationPresenter,
)
from substitute.presentation.canvas.input.input_mask_picker_presenter import (
    InputMaskPickerPresenter,
)
from substitute.presentation.canvas.input.input_mask_selection_presenter import (
    InputMaskSelectionPresenter,
)
from substitute.presentation.canvas.input.input_materialization_presenter import (
    InputMaterializationPresenter,
)
from substitute.presentation.canvas.input.input_node_preview_coordinator import (
    InputNodePreviewCoordinator,
)
from substitute.presentation.regional import region_color
from substitute.presentation.regional.mask_collection_presenter import (
    RegionalMaskCollectionPresenter,
)
from substitute.presentation.shell.input_canvas_shell_adapter import (
    InputCanvasShellAdapter,
)


@dataclass(frozen=True)
class InputPresentationComposition:
    """Hold direct Input presentation owners composed as one dependency graph."""

    images: InputImageMaterializationPresenter
    masks: InputMaskSelectionPresenter
    pickers: InputMaskPickerPresenter


def compose_input_presenters(
    *,
    shell: Any,
    input_canvas: Any,
    workflow_inputs: WorkflowInputCanvasService,
    shell_adapter: InputCanvasShellAdapter,
    regional_masks: RegionalMaskCollectionPresenter,
    preview_coordinator: InputNodePreviewCoordinator,
) -> InputPresentationComposition:
    """Compose direct Input presenters around shared result projection."""

    pickers = InputMaskPickerPresenter(
        active_workflow=shell.get_active_workflow,
        active_panel=lambda: shell.active_editor_panel,
        workflow_session=shell.workflow_session_service,
        workflow_inputs=workflow_inputs,
        workflow_name=shell_adapter.resolve_workflow_name,
        projects_dir=lambda: Path(shell.path_bundle.projects_dir),
        preview_coordinator=preview_coordinator,
    )
    materialization = InputMaterializationPresenter(
        input_document=input_canvas.document,
        active_workflow=shell.get_active_workflow,
        active_panel=lambda: shell.active_editor_panel,
        mask_color=region_color,
        refresh_scalar_mask=lambda cube_alias, node_name, projects_dir: pickers.refresh(
            cube_alias,
            node_name,
            projects_dir=projects_dir,
        ),
        refresh_ordered_mask=regional_masks.refresh,
        activate_mask=lambda workflow, mask_id: shell.input_routes.set_active_mask(
            shell.workflow_session_service.active_workflow_id,
            workflow,
            mask_id,
        ),
        preview_coordinator=preview_coordinator,
    )
    images = InputImageMaterializationPresenter(
        current_image_id=input_canvas.current_image_id_for_event,
        active_workflow=shell.get_active_workflow,
        active_panel=lambda: shell.active_editor_panel,
        workflow_session=shell.workflow_session_service,
        workflow_inputs=workflow_inputs,
        input_state=shell.input_image_assets,
        workflow_name=shell_adapter.resolve_workflow_name,
        projects_dir=lambda: Path(shell.path_bundle.projects_dir),
        materialization=materialization,
        preview_coordinator=preview_coordinator,
        mark_changed=shell_adapter.mark_input_canvas_changed,
    )
    masks = InputMaskSelectionPresenter(
        active_workflow=shell.get_active_workflow,
        workflow_session=shell.workflow_session_service,
        workflow_inputs=workflow_inputs,
        workflow_name=shell_adapter.resolve_workflow_name,
        projects_dir=lambda: Path(shell.path_bundle.projects_dir),
        materialization=materialization,
        mask_pickers=pickers,
        mark_changed=shell_adapter.mark_input_canvas_changed,
        error_presenter=getattr(shell, "_error_presenter", None),
    )
    return InputPresentationComposition(images=images, masks=masks, pickers=pickers)


__all__ = ["InputPresentationComposition", "compose_input_presenters"]
