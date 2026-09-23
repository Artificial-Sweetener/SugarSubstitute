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

"""Own Input mask visual-opacity state and document synchronization."""

from __future__ import annotations

import math
from uuid import UUID

from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_mask_layer_removal import (
    mask_ids_for_association,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.workflows.input_mask_visual_state_service")


class InputMaskVisualStateService:
    """Synchronize node-owned mask opacity across state and live layers."""

    def __init__(self, document: InputCanvasDocumentPort) -> None:
        """Store the live Input document opacity boundary."""

        self._document = document

    def set_opacity(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Apply one node-owned visual opacity atomically to all of its masks."""

        normalized = _normalized_opacity(opacity)
        if normalized is None:
            log_warning(
                _LOGGER,
                "Rejected invalid Input mask visual opacity",
                workflow_id=workflow_id,
                association_key=association_key,
                opacity=opacity,
                rejection_reason="invalid_opacity",
            )
            return False
        previous_opacity = workflow.canvas.mask_visual_opacity(association_key)
        updated_mask_ids: list[UUID] = []
        for mask_id in mask_ids_for_association(workflow, association_key):
            if self._document.set_mask_visual_opacity(mask_id, normalized):
                updated_mask_ids.append(mask_id)
                continue
            for updated_mask_id in updated_mask_ids:
                self._document.set_mask_visual_opacity(
                    updated_mask_id,
                    previous_opacity,
                )
            log_warning(
                _LOGGER,
                "Failed to apply Input mask visual opacity",
                workflow_id=workflow_id,
                association_key=association_key,
                mask_id=str(mask_id),
                opacity=normalized,
                rejection_reason="document_rejected_opacity",
            )
            return False
        workflow.canvas.set_mask_visual_opacity(association_key, normalized)
        log_debug(
            _LOGGER,
            "Applied Input mask visual opacity",
            workflow_id=workflow_id,
            association_key=association_key,
            opacity=normalized,
            mask_count=len(updated_mask_ids),
        )
        return True

    @staticmethod
    def mask_ids(
        workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> tuple[UUID, ...]:
        """Return every materialized mask owned by one graph mask node."""

        return mask_ids_for_association(workflow, association_key)

    def synchronize_restored_opacity(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Adopt one opacity already restored by document history."""

        normalized = _normalized_opacity(opacity)
        if normalized is None:
            log_warning(
                _LOGGER,
                "Rejected invalid mask opacity restored by document history",
                workflow_id=workflow_id,
                association_key=association_key,
                opacity=opacity,
                rejection_reason="invalid_history_opacity",
            )
            return False
        if workflow.canvas.mask_visual_opacity(association_key) == normalized:
            return False
        workflow.canvas.set_mask_visual_opacity(association_key, normalized)
        log_debug(
            _LOGGER,
            "Synchronized mask opacity restored by document history",
            workflow_id=workflow_id,
            association_key=association_key,
            opacity=normalized,
        )
        return True

    def apply_materialized_opacity(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        mask_id: UUID,
    ) -> bool:
        """Apply an explicit node value to one newly materialized mask."""

        opacity = workflow.canvas.mask_visual_opacities.get(association_key)
        if opacity is None:
            return True
        if mask_id not in mask_ids_for_association(workflow, association_key):
            log_warning(
                _LOGGER,
                "Rejected Input mask opacity projection for foreign association",
                workflow_id=workflow_id,
                association_key=association_key,
                mask_id=str(mask_id),
                rejection_reason="mask_association_mismatch",
            )
            return False
        applied = self._document.set_mask_visual_opacity(mask_id, opacity)
        if not applied:
            log_warning(
                _LOGGER,
                "Failed to project stored Input mask visual opacity",
                workflow_id=workflow_id,
                association_key=association_key,
                mask_id=str(mask_id),
                opacity=opacity,
                rejection_reason="document_rejected_opacity",
            )
        return applied


def _normalized_opacity(opacity: float) -> float | None:
    """Return a finite normalized opacity or reject invalid input."""

    try:
        normalized = float(opacity)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        return None
    return normalized


__all__ = ["InputMaskVisualStateService"]
