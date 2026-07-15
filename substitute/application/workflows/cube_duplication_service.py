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

"""Duplicate one complete cube instance inside a workflow."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from substitute.application.cubes.cube_stack_service import CubeStackService
from substitute.application.cubes.cube_state_duplicator import CubeStateDuplicator
from substitute.application.workflows.workflow_asset_service import (
    CubeAssetAssociationCopyResult,
    WorkflowAssetService,
)
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_info,
    log_warning,
)

_LOGGER = get_logger("application.workflows.cube_duplication_service")
_SLOW_DUPLICATION_MS = 100.0


class CubeLinkReconcilerProtocol(Protocol):
    """Describe link normalization required after cube-stack mutation."""

    def reconcile_transition(
        self,
        *,
        previous_cube_states: dict[str, CubeState],
        previous_stack_order: list[str],
        current_cube_states: dict[str, CubeState],
        current_stack_order: list[str],
    ) -> None:
        """Reconcile links across a workflow transition."""

    def sanitize_current_state(
        self,
        *,
        cube_states: dict[str, CubeState],
        stack_order: list[str],
    ) -> None:
        """Normalize links in the current workflow state."""


@dataclass(frozen=True, slots=True)
class CubeDuplicationResult:
    """Describe one completed durable cube duplication."""

    source_alias: str
    duplicate_alias: str
    duplicate_state: CubeState
    added_index: int
    asset_associations: CubeAssetAssociationCopyResult


class CubeDuplicationService:
    """Own complete workflow mutation for in-place cube duplication."""

    def __init__(
        self,
        *,
        cube_stack_service: CubeStackService,
        link_reconciler: CubeLinkReconcilerProtocol,
        state_duplicator: CubeStateDuplicator | None = None,
        asset_service: WorkflowAssetService | None = None,
    ) -> None:
        """Store mutation owners needed for deterministic duplication."""

        self._cube_stack_service = cube_stack_service
        self._link_reconciler = link_reconciler
        self._state_duplicator = state_duplicator or CubeStateDuplicator()
        self._asset_service = asset_service or WorkflowAssetService()

    def duplicate_cube(
        self,
        workflow: WorkflowState,
        source_alias: str,
    ) -> CubeDuplicationResult | None:
        """Append an independent source copy and reconcile workflow-owned state."""

        started_at = perf_counter()
        source = workflow.cubes.get(source_alias)
        if source is None:
            log_warning(
                _LOGGER,
                "Cube duplication skipped because source cube was missing",
                source_alias=source_alias,
                stack_order=list(workflow.stack_order),
            )
            return None

        previous_cube_states = dict(workflow.cubes)
        previous_stack_order = list(workflow.stack_order)
        duplicate_alias = self._cube_stack_service.resolve_unique_alias(
            workflow,
            source_alias,
        )
        duplicate = self._state_duplicator.duplicate_as(source, duplicate_alias)
        self._cube_stack_service.apply_cube_addition(
            workflow,
            duplicate.cube_id,
            duplicate_alias,
            duplicate,
        )
        asset_associations = self._asset_service.duplicate_cube_associations(
            workflow,
            source_alias=source_alias,
            target_alias=duplicate_alias,
        )
        self._link_reconciler.reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=workflow.cubes,
            current_stack_order=list(workflow.stack_order),
        )
        self._link_reconciler.sanitize_current_state(
            cube_states=workflow.cubes,
            stack_order=list(workflow.stack_order),
        )
        added_index = workflow.stack_order.index(duplicate_alias)
        result = CubeDuplicationResult(
            source_alias=source_alias,
            duplicate_alias=duplicate_alias,
            duplicate_state=duplicate,
            added_index=added_index,
            asset_associations=asset_associations,
        )
        elapsed_ms = elapsed_ms_since(started_at)
        context = {
            "source_alias": source_alias,
            "duplicate_alias": duplicate_alias,
            "cube_id": duplicate.cube_id,
            "added_index": added_index,
            "input_image_association_count": asset_associations.input_image_count,
            "input_mask_association_count": asset_associations.input_mask_count,
            "elapsed_ms": f"{elapsed_ms:.3f}",
        }
        if elapsed_ms >= _SLOW_DUPLICATION_MS:
            log_warning(_LOGGER, "Cube duplication completed slowly", **context)
        else:
            log_info(_LOGGER, "Cube duplication completed", **context)
        return result


__all__ = [
    "CubeDuplicationResult",
    "CubeDuplicationService",
    "CubeLinkReconcilerProtocol",
]
