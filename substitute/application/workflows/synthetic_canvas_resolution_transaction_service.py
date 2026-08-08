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

"""Guard and project synthetic canvas resolution graph transactions."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
    SyntheticCanvasResolutionRoleService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import CanvasDimensions, WorkflowState
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger(
    "application.workflows.synthetic_canvas_resolution_transaction_service"
)


class SyntheticCanvasResolutionStaleError(RuntimeError):
    """Report that graph authority changed after the dialog opened."""


class SyntheticCanvasResolutionProjectionError(RuntimeError):
    """Report that validated authority fields could not be projected atomically."""


@dataclass(frozen=True, slots=True)
class SyntheticCanvasResolutionProjection:
    """Describe one successfully projected authority size."""

    role: SyntheticCanvasResolutionRole
    dimensions: CanvasDimensions


class SyntheticCanvasResolutionTransactionService:
    """Validate authority snapshots and atomically project resulting dimensions."""

    def __init__(
        self,
        *,
        roles: SyntheticCanvasResolutionRoleService,
        graph_sections: WorkflowGraphSectionService,
    ) -> None:
        """Store semantic resolution and graph mutation owners."""

        self._roles = roles
        self._graph_sections = graph_sections

    def validate(
        self,
        workflow: WorkflowState,
        expected: SyntheticCanvasResolutionRole,
    ) -> SyntheticCanvasResolutionRole:
        """Return current authority only when structural and dimension state match."""

        graph = self._graph_sections.graph(workflow, expected.section_key)
        first_node = (
            expected.authority.node_names[0] if expected.authority.node_names else ""
        )
        current = (
            self._roles.resolve_for_node(
                section_key=expected.section_key,
                graph=graph,
                node_name=first_node,
            )
            if graph is not None and first_node
            else None
        )
        if (
            current is None
            or current.surface_key != expected.surface_key
            or current.authority.structural_fingerprint
            != expected.authority.structural_fingerprint
            or current.authority.dimension_fingerprint
            != expected.authority.dimension_fingerprint
        ):
            log_warning(
                _LOGGER,
                "Rejected stale synthetic canvas resolution authority",
                section_key=expected.section_key,
                canvas_surface_key=expected.surface_key,
                expected_structural_fingerprint=expected.authority.structural_fingerprint,
                current_structural_fingerprint=(
                    current.authority.structural_fingerprint if current else ""
                ),
            )
            raise SyntheticCanvasResolutionStaleError(
                "Synthetic canvas resolution authority changed"
            )
        return current

    def project(
        self,
        workflow: WorkflowState,
        *,
        expected: SyntheticCanvasResolutionRole,
        dimensions: CanvasDimensions,
    ) -> SyntheticCanvasResolutionProjection:
        """Project a successful canvas size into every authority field atomically."""

        current = self.validate(workflow, expected)
        values = tuple(
            field_value
            for node_name, (width_key, height_key) in zip(
                current.authority.node_names,
                current.authority.field_pairs,
                strict=True,
            )
            for field_value in (
                (node_name, width_key, dimensions.width),
                (node_name, height_key, dimensions.height),
            )
        )
        mutation = self._graph_sections.set_input_values_atomic(
            workflow,
            section_key=current.section_key,
            values=values,
        )
        if not mutation.changed:
            raise SyntheticCanvasResolutionProjectionError(
                "Synthetic canvas authority fields are no longer writable"
            )
        log_info(
            _LOGGER,
            "Projected synthetic canvas resolution into graph authority",
            section_key=current.section_key,
            canvas_surface_key=current.surface_key,
            authority_nodes=current.authority.node_names,
            width=dimensions.width,
            height=dimensions.height,
        )
        return SyntheticCanvasResolutionProjection(
            role=current,
            dimensions=dimensions,
        )


__all__ = [
    "SyntheticCanvasResolutionProjection",
    "SyntheticCanvasResolutionProjectionError",
    "SyntheticCanvasResolutionStaleError",
    "SyntheticCanvasResolutionTransactionService",
]
