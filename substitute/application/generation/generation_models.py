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

"""Define lightweight generation request, callback, and result models."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sugarsubstitute_shared.localization import ApplicationText

from substitute.application.errors import ErrorReport
from substitute.application.ports.comfy_gateway import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.domain.common import WorkflowId
from substitute.domain.comfy_workflow import DirectWorkflowGenerationPlan

if TYPE_CHECKING:
    from substitute.application.recipes.recipe_io_service import (
        WorkflowLike as RecipeWorkflowLike,
    )


@dataclass(frozen=True)
class PreparedGenerationRequest:
    """Capture generation-ready recipe text independent from live workflow state."""

    workflow_id: WorkflowId
    workflow_name: str
    sugar_script_text: str
    direct_workflow_plan: DirectWorkflowGenerationPlan | None = None
    workflow: RecipeWorkflowLike | None = None
    output_run_number: int | None = None
    output_job_started_at: datetime | None = None
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


@dataclass(frozen=True)
class GenerationFailure:
    """Represent generation failures with stage-specific context."""

    stage: str
    workflow_id: WorkflowId
    message: ApplicationText
    generation_run_id: str | None = None
    prompt_id: str | None = None
    client_id: str | None = None
    detail: str | None = None
    error_report: ErrorReport | None = None


@dataclass(frozen=True)
class GenerationRunStarted:
    """Identify one prompt-bound generation run before visual events arrive."""

    workflow_id: WorkflowId
    generation_run_id: str
    prompt_id: str
    client_id: str


@dataclass(frozen=True)
class GenerationStartResult:
    """Capture generation dispatch success or failure outcome."""

    started: bool
    prompt_id: str | None
    failure: GenerationFailure | None
    generation_run_id: str | None = None
    client_id: str | None = None


@dataclass
class GenerationCallbacks:
    """Define application-facing callbacks for generation event propagation."""

    clear_output: Callable[[WorkflowId], None]
    on_progress: Callable[[ProgressUpdate], None]
    on_model_load_progress: Callable[[ModelLoadProgressUpdate], None]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_output_image: Callable[[OutputImageUpdate], None]
    on_failure: Callable[[GenerationFailure], None]
    on_timing: Callable[[GenerationExecutionTiming], None]
    on_run_started: Callable[[GenerationRunStarted], None] | None = None
    randomize_seeds: Callable[[], None] | None = None
    on_completed: Callable[[ListenerCompleted], None] | None = None


__all__ = [
    "GenerationCallbacks",
    "GenerationFailure",
    "GenerationRunStarted",
    "GenerationStartResult",
    "PreparedGenerationRequest",
]
