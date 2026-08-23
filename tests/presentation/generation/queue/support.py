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

"""Build deterministic queue state and record queue-surface commands."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from substitute.application.generation import GenerationQueueStateChange
from substitute.domain.generation import GenerationJobSnapshot, GenerationQueueJob

QueueStatus = Literal[
    "pending",
    "dispatching",
    "comfy_pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]


def queue_job(
    job_id: str,
    *,
    status: QueueStatus,
    prompt_id: str | None = None,
    failure_message: str | None = None,
    failure_summary: str | None = None,
    failure_detail: str | None = None,
    last_output_path: Path | None = None,
    output_run_number: int | None = None,
    projected_output_run_number: int | None = None,
    progress_percent: float | None = None,
    output_count: int = 0,
    execution_duration_ms: float | None = None,
    created_at: datetime | None = None,
    workflow_name: str | None = None,
    positive_prompt_preview: str | None = None,
    output_bucket_key: str | None = None,
    output_bucket_label: str | None = None,
    projected_output_bucket_key: str | None = None,
    projected_output_bucket_label: str | None = None,
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
) -> GenerationQueueJob:
    """Build one queue job DTO for presentation contracts."""

    resolved_workflow_name = workflow_name or f"Workflow {job_id}"
    return GenerationQueueJob(
        job_id=job_id,
        snapshot=GenerationJobSnapshot(
            workflow_id=f"workflow-{job_id}",
            workflow_name=resolved_workflow_name,
            sugar_script_text="# sugar",
            positive_prompt_preview=positive_prompt_preview,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
        ),
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=status,
        prompt_id=prompt_id,
        failure_message=failure_message,
        failure_summary=failure_summary,
        failure_detail=failure_detail,
        output_run_number=output_run_number,
        projected_output_run_number=projected_output_run_number,
        output_bucket_key=output_bucket_key,
        output_bucket_label=output_bucket_label,
        projected_output_bucket_key=projected_output_bucket_key,
        projected_output_bucket_label=projected_output_bucket_label,
        progress_percent=progress_percent,
        output_count=output_count,
        execution_duration_ms=execution_duration_ms,
        last_output_path=last_output_path,
    )


class RecordingQueueService:
    """Publish queue state and record commands crossing the presentation boundary."""

    def __init__(self, jobs: tuple[GenerationQueueJob, ...] = ()) -> None:
        """Store initial jobs and empty command records."""

        self.jobs = jobs
        self.cancelled: list[str] = []
        self.removed: list[str] = []
        self.moved: list[tuple[str, int]] = []
        self.observers: list[Callable[[GenerationQueueStateChange], None]] = []

    def add_observer(
        self,
        observer: Callable[[GenerationQueueStateChange], None],
    ) -> None:
        """Register an observer and publish the current structural state."""

        self.observers.append(observer)
        observer(GenerationQueueStateChange(jobs=self.jobs, change_kind="structural"))

    def remove_observer(
        self,
        observer: Callable[[GenerationQueueStateChange], None],
    ) -> None:
        """Remove one registered observer."""

        self.observers.remove(observer)

    def cancel_job(self, job_id: str) -> None:
        """Record one cancellation command."""

        self.cancelled.append(job_id)

    def remove_terminal_job(self, job_id: str) -> None:
        """Record one terminal-row removal command."""

        self.removed.append(job_id)

    def move_pending_job(self, job_id: str, target_index: int) -> None:
        """Record one pending-row reorder command."""

        self.moved.append((job_id, target_index))
