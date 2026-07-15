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

"""Clone workflow authoring state for tab duplication."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from time import perf_counter

from substitute.application.cubes import CubeStateDuplicator
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_info,
    log_warning,
)

_LOGGER = get_logger("application.workflows.workflow_duplicate_service")
_SLOW_DUPLICATE_CLONE_MS = 100.0


class WorkflowDuplicateService:
    """Clone durable workflow state while resetting volatile session state."""

    def __init__(
        self,
        clock: Callable[[], float] = perf_counter,
        cube_state_duplicator: CubeStateDuplicator | None = None,
    ) -> None:
        """Create service with injectable monotonic clock for diagnostics."""

        self._clock = clock
        self._cube_state_duplicator = cube_state_duplicator or CubeStateDuplicator()

    def duplicate_workflow(self, source: WorkflowState) -> WorkflowState:
        """Return an independent workflow copy with live UI state reset."""

        started_at = self._clock()
        cube_count = len(source.cubes)
        stack_order_count = len(source.stack_order)
        log_info(
            _LOGGER,
            "Workflow duplicate clone started",
            cube_count=cube_count,
            stack_order_count=stack_order_count,
            metadata_key_count=len(source.metadata),
            global_override_count=len(source.global_overrides),
            global_override_selection_count=len(source.global_override_selections),
            source_canvas_input_count=len(source.canvas.input_key_map),
            source_canvas_mask_count=len(source.canvas.mask_associations),
            source_output_count=len(source.output_image_uuids),
        )
        duplicate = WorkflowState(
            cubes={
                alias: self._cube_state_duplicator.duplicate_as(cube_state, alias)
                for alias, cube_state in source.cubes.items()
            },
            stack_order=list(source.stack_order),
            metadata=deepcopy(source.metadata),
            global_overrides=deepcopy(source.global_overrides),
            override_control_states=deepcopy(source.override_control_states),
            global_override_selections=deepcopy(source.global_override_selections),
        )
        elapsed_ms = elapsed_ms_since(started_at, clock=self._clock)
        log_context = {
            "elapsed_ms": f"{elapsed_ms:.3f}",
            "cube_count": len(duplicate.cubes),
            "stack_order_count": len(duplicate.stack_order),
            "metadata_key_count": len(duplicate.metadata),
            "global_override_count": len(duplicate.global_overrides),
            "global_override_selection_count": len(
                duplicate.global_override_selections
            ),
            "canvas_input_reset": duplicate.canvas.input_key_map == {},
            "canvas_mask_reset": duplicate.canvas.mask_associations == {},
            "output_history_reset": duplicate.output_image_uuids == [],
        }
        if elapsed_ms >= _SLOW_DUPLICATE_CLONE_MS:
            log_warning(
                _LOGGER,
                "Workflow duplicate clone was slow",
                **log_context,
            )
        else:
            log_info(
                _LOGGER,
                "Workflow duplicate clone completed",
                **log_context,
            )
        return duplicate
