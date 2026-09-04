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

"""Build generation-ready requests from committed queue snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from substitute.application.generation.generation_models import (
    PreparedGenerationRequest,
)
from substitute.domain.generation import GenerationJobSnapshot

if TYPE_CHECKING:
    from substitute.application.recipes.recipe_io_service import WorkflowLike


def prepared_request_from_queue_snapshot(
    snapshot: GenerationJobSnapshot,
    *,
    output_run_number: int | None,
    job_started_at: datetime,
) -> PreparedGenerationRequest:
    """Preserve every immutable queue and Output-session identity for dispatch."""

    return PreparedGenerationRequest(
        workflow_id=snapshot.workflow_id,
        workflow_name=snapshot.workflow_name,
        sugar_script_text=snapshot.sugar_script_text,
        direct_workflow_plan=snapshot.direct_workflow_plan,
        workflow=cast("WorkflowLike | None", snapshot.workflow),
        output_run_number=output_run_number,
        output_job_started_at=job_started_at,
        output_session_id=snapshot.output_session_id,
        scene_run_id=snapshot.scene_run_id,
        scene_key=snapshot.scene_key,
        scene_title=snapshot.scene_title,
        scene_order=snapshot.scene_order,
        scene_count=snapshot.scene_count,
    )


__all__ = ["prepared_request_from_queue_snapshot"]
