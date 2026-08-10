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

"""Apply late generation timing to registered Output metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_state_service import (
    OutputProjectionSchedulingIntent,
)
from substitute.domain.workflow import ImageMeta, WorkflowState


@dataclass(frozen=True, slots=True)
class OutputTimingUpdateResult:
    """Describe Output metadata timing updates."""

    workflow_id: str
    updated_image_ids: tuple[UUID, ...]
    projection_intent: OutputProjectionSchedulingIntent

    @property
    def changed(self) -> bool:
        """Return whether any Output metadata changed."""

        return bool(self.updated_image_ids)


class OutputCanvasTimingService:
    """Own late execution-duration updates for registered Output metadata."""

    def __init__(self, *, image_registry: CanvasImageRegistry) -> None:
        """Store the authoritative Output metadata registry."""

        self._image_registry = image_registry

    def apply_output_source_timing(
        self,
        workflows: Mapping[str, WorkflowState],
        *,
        workflow_id: str,
        active_workflow_id: str,
        source_durations_ms: Mapping[str, float],
        cube_durations_ms: Mapping[str, float],
    ) -> OutputTimingUpdateResult:
        """Apply source timing to existing Output metadata records."""

        workflow = workflows.get(workflow_id)
        if workflow is None:
            return OutputTimingUpdateResult(
                workflow_id=workflow_id,
                updated_image_ids=(),
                projection_intent=OutputProjectionSchedulingIntent.none(workflow_id),
            )
        updated_image_ids: list[UUID] = []
        for image_id in workflow.output_image_uuids:
            image_meta = self._image_registry.metadata_for(image_id)
            if image_meta is None:
                continue
            duration_ms = _duration_for_image_meta(
                image_meta,
                source_durations_ms=source_durations_ms,
                cube_durations_ms=cube_durations_ms,
            )
            if (
                duration_ms is None
                or image_meta.cube_execution_duration_ms == duration_ms
            ):
                continue
            image_meta.cube_execution_duration_ms = duration_ms
            updated_image_ids.append(image_id)
        return OutputTimingUpdateResult(
            workflow_id=workflow_id,
            updated_image_ids=tuple(updated_image_ids),
            projection_intent=OutputProjectionSchedulingIntent(
                workflow_id=workflow_id,
                registered_image_id=None,
                should_schedule=bool(updated_image_ids)
                and workflow_id == active_workflow_id,
            ),
        )


def _duration_for_image_meta(
    image_meta: ImageMeta,
    *,
    source_durations_ms: Mapping[str, float],
    cube_durations_ms: Mapping[str, float],
) -> float | None:
    """Return a matching timing duration for one Output metadata record."""

    if image_meta.source_key in source_durations_ms:
        return source_durations_ms[image_meta.source_key]
    if image_meta.source_label in cube_durations_ms:
        return cube_durations_ms[image_meta.source_label]
    if image_meta.cube_name in cube_durations_ms:
        return cube_durations_ms[image_meta.cube_name]
    return None


__all__ = ["OutputCanvasTimingService", "OutputTimingUpdateResult"]
