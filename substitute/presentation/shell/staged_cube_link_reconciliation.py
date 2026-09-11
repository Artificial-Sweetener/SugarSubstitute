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

"""Reconcile workflow links after committed staged Cube loads."""

from __future__ import annotations

from substitute.application.workflows import CubeLinkReconcilerProtocol
from substitute.domain.workflow import CubeState
from substitute.presentation.shell.deferred_workflow_link_reconciler import (
    DeferredWorkflowLinkReconciler,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.shell.staged_cube_link_reconciliation")


class StagedCubeLinkReconciliationCoordinator:
    """Apply link reconciliation only after at least one staged load commits."""

    def __init__(
        self,
        provider_owner: object,
        *,
        link_reconciler: CubeLinkReconcilerProtocol | None = None,
    ) -> None:
        """Store the link reconciler, resolving the live provider by default."""

        self._link_reconciler = link_reconciler or DeferredWorkflowLinkReconciler(
            provider_owner
        )

    def reconcile_committed_transition(
        self,
        *,
        previous_cube_states: dict[str, CubeState],
        previous_stack_order: list[str],
        current_cube_states: dict[str, CubeState],
        current_stack_order: list[str],
        completed_staged_count: int,
        failed_queue_count: int,
        workflow_id: str,
        trace_id: str,
        is_batch_load: bool,
    ) -> bool:
        """Reconcile a committed transition and report whether work occurred."""

        if completed_staged_count <= 0:
            return False
        self._link_reconciler.reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=current_cube_states,
            current_stack_order=current_stack_order,
        )
        self._link_reconciler.sanitize_current_state(
            cube_states=current_cube_states,
            stack_order=current_stack_order,
        )
        log_info(
            _LOGGER,
            "Reconciled staged Cube link state",
            cube_load_trace_id=trace_id,
            workflow_id=workflow_id,
            previous_stack_order_count=len(previous_stack_order),
            final_stack_order_count=len(current_stack_order),
            completed_staged_count=completed_staged_count,
            failed_queue_count=failed_queue_count,
            is_batch_load=is_batch_load,
        )
        return True


__all__ = ["StagedCubeLinkReconciliationCoordinator"]
