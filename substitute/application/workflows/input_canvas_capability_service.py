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

"""Resolve whether workflows expose input-canvas interactions."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.cubes import CubeMaskBindingService
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger

_LOGGER = get_logger("application.workflows.input_canvas_capability_service")


class InputCanvasCapabilityService:
    """Resolve active workflow capability for the shared Input canvas."""

    def __init__(self, cube_mask_binding_service: CubeMaskBindingService) -> None:
        """Capture the binding service used for editable mask detection."""

        self._cube_mask_binding_service = cube_mask_binding_service

    def workflow_needs_input_canvas(self, workflow: WorkflowState | None) -> bool:
        """Return whether a workflow should expose input-canvas UI."""

        if workflow is None:
            return False
        for cube_alias, cube_state in workflow.cubes.items():
            cube_graph = cube_state.buffer
            if self._has_load_image_asset_field(cube_graph):
                return True
            binding_index = self._cube_mask_binding_service.build_index(
                cube_alias,
                cube_graph,
            )
            if binding_index.bindings:
                return True
        return False

    @staticmethod
    def _has_load_image_asset_field(cube_graph: Mapping[str, object]) -> bool:
        """Return whether a cube graph contains a LoadImage image input."""

        nodes = cube_graph.get("nodes", {})
        if not isinstance(nodes, Mapping):
            return False
        for node_data in nodes.values():
            if not isinstance(node_data, Mapping):
                continue
            if node_data.get("class_type") != "LoadImage":
                continue
            inputs = node_data.get("inputs", {})
            if isinstance(inputs, Mapping) and "image" in inputs:
                return True
        return False


__all__ = ["InputCanvasCapabilityService"]
