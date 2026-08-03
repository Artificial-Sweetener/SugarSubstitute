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

"""Own editor Input-node selection, activation, and editing navigation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeGuard
from uuid import UUID

from PySide6.QtCore import QTimer

from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_node_interaction_controller")


class _WorkflowInputCanvasServicePort(Protocol):
    """Describe graph binding queries required by picker interaction."""

    def bindings_for_image(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        image_node_name: str,
    ) -> tuple[object, ...]:
        """Return mask bindings owned by one image node."""

    def binding_for_mask(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        mask_node_name: str,
    ) -> object | None:
        """Return the authoritative binding for one mask node."""


class _InputCanvasStateServicePort(Protocol):
    """Describe authoritative Input selection mutations."""

    def set_active_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Activate one workflow-owned image."""

    def set_active_workflow_mask(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Activate one workflow-owned mask."""


class InputNodeInteractionController:
    """Coordinate picker intent through graph identity and canvas route owners."""

    def __init__(
        self,
        *,
        active_workflow: Callable[[], WorkflowState | None],
        active_workflow_id: Callable[[], str],
        workflow_input_canvas_service: _WorkflowInputCanvasServicePort,
        input_canvas_state_service: _InputCanvasStateServicePort,
        materialize_image_selection: Callable[[str, str, str], bool],
        apply_mask_selection: Callable[[str, str, str], bool],
        activate_input_canvas: Callable[[], bool],
        refresh_mask_pickers: Callable[[], None],
        tool_controller: InputCanvasToolController,
    ) -> None:
        """Store the single owners participating in Input-node interactions."""

        self._active_workflow = active_workflow
        self._active_workflow_id = active_workflow_id
        self._workflow_input_canvas_service = workflow_input_canvas_service
        self._input_canvas_state_service = input_canvas_state_service
        self._materialize_image_selection = materialize_image_selection
        self._apply_mask_selection = apply_mask_selection
        self._activate_input_canvas = activate_input_canvas
        self._refresh_mask_pickers = refresh_mask_pickers
        self._tool_controller = tool_controller

    def handle_image_changed(
        self,
        cube_alias: str,
        node_name: str,
        image_path: str,
    ) -> None:
        """Materialize a selected image and enter its Input editing route."""

        if self._materialize_image_selection(cube_alias, node_name, image_path):
            self._activate_input_canvas()

    def handle_mask_changed(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> None:
        """Apply one selected mask through the materialization presenter."""

        self._apply_mask_selection(cube_alias, node_name, mask_path)

    def handle_image_clicked(
        self,
        cube_alias: str,
        node_name: str,
        _image_path: str,
    ) -> None:
        """Activate the clicked image, its first mask, and keyboard editing focus."""

        workflow = self._active_workflow()
        if workflow is None:
            return
        workflow_id = self._active_workflow_id()
        image_entry = workflow.canvas.image_entry(f"{cube_alias}:{node_name}")
        if image_entry is None:
            return
        image_id = image_entry.image_id
        if not self._input_canvas_state_service.set_active_input_image(
            workflow_id,
            workflow,
            image_id,
        ):
            return
        bindings = self._workflow_input_canvas_service.bindings_for_image(
            workflow,
            cube_alias,
            node_name,
        )
        if bindings:
            association_key = getattr(bindings[0], "association_key", None)
            mask_entry = (
                workflow.canvas.mask_entry(association_key)
                if _association_key(association_key)
                else None
            )
            if mask_entry is not None:
                self._input_canvas_state_service.set_active_workflow_mask(
                    workflow_id,
                    workflow,
                    mask_entry.mask_id,
                )
        self._activate_input_canvas()
        QTimer.singleShot(0, self._refresh_mask_pickers)

    def handle_mask_clicked(
        self,
        cube_alias: str,
        node_name: str,
        _mask_path: str,
    ) -> None:
        """Activate the exact owning image and mask, focus Input, and select Brush."""

        workflow = self._active_workflow()
        if workflow is None:
            return
        workflow_id = self._active_workflow_id()
        binding = self._workflow_input_canvas_service.binding_for_mask(
            workflow,
            cube_alias,
            node_name,
        )
        if binding is None:
            self._log_rejection(
                workflow_id, cube_alias, node_name, "missing_mask_binding"
            )
            return
        section_key = getattr(binding, "section_key", None)
        surface_key = getattr(binding, "surface_key", None)
        association_key = getattr(binding, "association_key", None)
        if not isinstance(section_key, str) or not isinstance(surface_key, str):
            return
        image_entry = workflow.canvas.image_entry(f"{section_key}:{surface_key}")
        if image_entry is None:
            self._log_rejection(
                workflow_id,
                cube_alias,
                node_name,
                "missing_bound_input_image",
            )
            return
        image_id = image_entry.image_id
        if not self._input_canvas_state_service.set_active_input_image(
            workflow_id,
            workflow,
            image_id,
        ):
            return
        if not _association_key(association_key):
            self._log_rejection(
                workflow_id, cube_alias, node_name, "invalid_mask_binding"
            )
            return
        mask_entry = workflow.canvas.mask_entry(association_key)
        if mask_entry is None:
            self._log_rejection(
                workflow_id, cube_alias, node_name, "missing_canvas_mask"
            )
            return
        mask_id = mask_entry.mask_id
        if not self._input_canvas_state_service.set_active_workflow_mask(
            workflow_id,
            workflow,
            mask_id,
        ):
            return
        self._activate_input_canvas()
        self._tool_controller.request_brush_after_mask_activation()

    @staticmethod
    def _log_rejection(
        workflow_id: str,
        cube_alias: str,
        node_name: str,
        reason: str,
    ) -> None:
        """Log one graph-identity rejection with actionable node context."""

        log_warning(
            _LOGGER,
            "Rejected Input node interaction",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            node_name=node_name,
            rejection_reason=reason,
        )


def _association_key(value: object) -> TypeGuard[tuple[str, str]]:
    """Return whether one binding exposes a concrete graph association key."""

    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    )


__all__ = ["InputNodeInteractionController"]
