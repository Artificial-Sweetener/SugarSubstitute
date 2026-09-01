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

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.application.generation import (
    GenerationFailure,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
    GenerationRunStarted,
)
from substitute.application.errors import ErrorReport
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)

class GenerationUiBindings:
    build_generation_request: Callable[[], GenerationRequest]
    randomize_seeds: Callable[[], None]
    on_progress: Callable[[ProgressUpdate], None]
    on_model_load_progress: Callable[[ModelLoadProgressUpdate], None]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_output_image: Callable[[OutputImageUpdate], None]
    on_failure: Callable[[GenerationFailure], None]
    on_timing: Callable[[GenerationExecutionTiming], None]
    on_completed: Callable[[ListenerCompleted], None]
    refresh_generation_actions: Callable[[], None]
    on_run_started: Callable[[GenerationRunStarted], None] | None
    effective_batch_count: Callable[[], int] | None
    build_queued_generation_snapshots: (
        Callable[[], tuple[GenerationJobSnapshot, ...]] | None
    )
    capture_queued_generation_preparation: Callable[[], object] | None
    def __init__(
        self,
        *,
        build_generation_request: Callable[[], GenerationRequest],
        randomize_seeds: Callable[[], None],
        on_progress: Callable[[ProgressUpdate], None],
        on_model_load_progress: Callable[[ModelLoadProgressUpdate], None],
        on_preview: Callable[[PreviewImageUpdate], None],
        on_output_image: Callable[[OutputImageUpdate], None],
        on_failure: Callable[[GenerationFailure], None],
        on_timing: Callable[[GenerationExecutionTiming], None],
        on_completed: Callable[[ListenerCompleted], None],
        refresh_generation_actions: Callable[[], None],
        on_run_started: Callable[[GenerationRunStarted], None] | None = ...,
        effective_batch_count: Callable[[], int] | None = ...,
        build_queued_generation_snapshots: Callable[
            [], tuple[GenerationJobSnapshot, ...]
        ]
        | None = ...,
        capture_queued_generation_preparation: Callable[[], object] | None = ...,
    ) -> None: ...

class GenerationPreparationExecutor:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def close(self) -> None: ...
    def submit(
        self,
        *,
        prepare_snapshots: Callable[[], GenerationPreparationResult],
        on_completed: Callable[[GenerationPreparationResult], None],
        on_failed: Callable[[BaseException], None],
    ) -> None: ...

class GenerationPreflightError(RuntimeError):
    workflow_id: str
    error_report: ErrorReport | None
    report_error: bool
    def __init__(
        self,
        *,
        workflow_id: str,
        message: str,
        error_report: ErrorReport | None = ...,
        report_error: bool = ...,
    ) -> None: ...

class QueuedGenerationPreparationJob:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def prepare_snapshots(self) -> Any: ...
    def on_prepared(self, result: Any) -> tuple[GenerationJobSnapshot, ...]: ...

class WorkspaceGenerationController:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def handle_generate_clicked(self, *args: Any, **kwargs: Any) -> None: ...

def generation_preflight_failure(
    error: BaseException,
    *,
    operation: str,
) -> GenerationFailure: ...
