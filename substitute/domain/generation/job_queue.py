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

"""Define generation queue value objects independent from UI and transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Mapping
from typing import Literal

from sugarsubstitute_shared.localization import ApplicationText

from substitute.domain.comfy_workflow import DirectWorkflowGenerationPlan

GenerationJobStatus = Literal[
    "pending",
    "dispatching",
    "comfy_pending",
    "running",
    "completed",
    "failed",
    "cancelled",
]


@dataclass(frozen=True)
class GenerationJobSnapshot:
    """Store immutable workflow inputs captured when Generate was clicked."""

    workflow_id: str
    workflow_name: str
    sugar_script_text: str
    direct_workflow_plan: DirectWorkflowGenerationPlan | None = None
    positive_prompt_preview: str | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


@dataclass(frozen=True)
class GenerationQueueJob:
    """Describe one user-facing generation queue entry."""

    job_id: str
    snapshot: GenerationJobSnapshot
    created_at: datetime
    status: GenerationJobStatus
    prompt_id: str | None = None
    generation_run_id: str | None = None
    client_id: str | None = None
    failure_message: str | None = None
    failure_summary: ApplicationText | None = None
    failure_detail: str | None = None
    output_run_number: int | None = None
    projected_output_run_number: int | None = None
    output_bucket_key: str | None = None
    output_bucket_directory: Path | None = None
    output_bucket_label: str | None = None
    projected_output_bucket_key: str | None = None
    projected_output_bucket_directory: Path | None = None
    projected_output_bucket_label: str | None = None
    progress_percent: float | None = None
    output_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_output_path: Path | None = None
    last_output_node_id: str | None = None
    execution_duration_ms: float | None = None
    cube_execution_durations: tuple["GenerationCubeExecutionDuration", ...] = ()


@dataclass(frozen=True)
class GenerationCubeExecutionDuration:
    """Store one cube/source duration for a queued generation job."""

    cube_alias: str
    source_key: str
    duration_ms: float


@dataclass(frozen=True)
class GenerationJobOutputRecord:
    """Describe one output image produced by a live generation job."""

    job_id: str
    output_path: Path
    node_id: str
    created_at: datetime
    sequence: int
    source_key: str
    source_label: str
    scene_run_id: str | None
    scene_key: str | None
    scene_title: str | None
    scene_order: int | None
    scene_count: int | None
    node_title: str | None
    metadata: Mapping[str, object]


TERMINAL_GENERATION_JOB_STATUSES = frozenset({"completed", "failed", "cancelled"})


__all__ = [
    "GenerationJobSnapshot",
    "GenerationJobOutputRecord",
    "GenerationJobStatus",
    "GenerationCubeExecutionDuration",
    "GenerationQueueJob",
    "TERMINAL_GENERATION_JOB_STATUSES",
]
