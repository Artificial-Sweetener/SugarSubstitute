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

"""Build prompt-scene generation context without Qt dependencies."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast
from uuid import uuid4

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationCallbacks,
    GenerationFailure,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
    GenerationRunStarted,
)
from sugarsubstitute_shared.presentation.localization import (
    translate_application_message,
)
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.prompt_editor import (
    PromptSceneAnalysisService,
    WorkflowScene,
    WorkflowSceneAnalysis,
)

if TYPE_CHECKING:
    from substitute.application.node_behavior import EditorBehaviorSnapshot


class SceneGenerationPreflightErrorFactory(Protocol):
    """Create shell preflight exceptions for scene generation failures."""

    def __call__(self, *, workflow_id: str, message: str) -> Exception:
        """Return a preflight exception for one workflow failure."""


class SceneGenerationPreflightFailureFactory(Protocol):
    """Create generation failures from scene-generation preflight errors."""

    def __call__(
        self,
        error: Any,
        *,
        operation: str,
        values: dict[str, object] | None = None,
    ) -> GenerationFailure:
        """Return a generation failure for one preflight exception."""


class SceneGenerationSeedRandomizer(Protocol):
    """Randomize seed fields on a live scene generation request."""

    def __call__(
        self,
        *,
        request: GenerationRequest,
        behavior_snapshot: "EditorBehaviorSnapshot | None",
    ) -> None:
        """Apply seed randomization before request capture."""


class SceneGenerationPreparationService(Protocol):
    """Prepare immutable generation snapshots for prompt-scene requests."""

    def prepare_scene_snapshots(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_analysis: WorkflowSceneAnalysis | None = None,
        scene_run_id: str | None = None,
    ) -> GenerationPreparationResult:
        """Return one prepared snapshot for each runnable scene."""

    def prepare_scene_snapshot(
        self,
        *,
        request: CapturedGenerationRequest,
        scene_key: str,
        scene_run_id: str | None = None,
    ) -> GenerationJobSnapshot:
        """Return one prepared snapshot for a selected runnable scene."""


class SceneGenerationBindings(Protocol):
    """Expose shell callbacks needed to queue one prompt-scene snapshot."""

    randomize_seeds: Callable[[], None]
    clear_output_for_workflow: Callable[[str], None]
    on_progress: Callable[[ProgressUpdate], None]
    on_model_load_progress: Callable[[ModelLoadProgressUpdate], None]
    on_preview: Callable[[PreviewImageUpdate], None]
    on_output_image: Callable[[OutputImageUpdate], None]
    on_failure: Callable[[GenerationFailure], None]
    on_timing: Callable[[GenerationExecutionTiming], None]
    on_completed: Callable[[ListenerCompleted], None]
    on_run_started: Callable[[GenerationRunStarted], None] | None


class SceneGenerationFeedbackDispatcher(Protocol):
    """Report prompt-scene queueing failures to shell feedback."""

    def on_failure(self, failure: GenerationFailure) -> None:
        """Report one generation failure."""


class SceneRunBookkeepingCallback(Protocol):
    """Apply shell bookkeeping after a scene run is prepared."""

    def __call__(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...] = (),
    ) -> None:
        """Apply bookkeeping for a prepared scene generation run."""


class OutputSceneRunService(Protocol):
    """Record user-facing scene-run metadata for output navigation."""

    def start_scene_run(
        self,
        *,
        scene_run_id: str,
        workflow_id: str,
        workflow_name: str,
        scenes: Sequence[tuple[str | None, str | None, int]],
    ) -> None:
        """Start tracking one scene output run."""


class SceneOutputCanvasStateService(Protocol):
    """Record output generation state for scene-aware output canvases."""

    def begin_output_generation(
        self,
        workflows: Mapping[str, object],
        workflow_id: str,
        *,
        scene_run_id: str | None = None,
        scene_count: int | None = None,
    ) -> None:
        """Record that output generation began for a workflow."""


class SceneGenerationQueueService(Protocol):
    """Queue prepared prompt-scene snapshots for generation."""

    def enqueue_snapshot(
        self,
        snapshot: GenerationJobSnapshot,
        callbacks: GenerationCallbacks,
    ) -> None:
        """Enqueue one prompt-scene generation snapshot."""


class WorkspaceSceneGenerationActionView(Protocol):
    """Describe shell collaborators needed to enqueue prompt scenes."""

    generation_job_queue_service: object
    generation_feedback_dispatcher: SceneGenerationFeedbackDispatcher


@dataclass(frozen=True, slots=True)
class SceneGenerationContext:
    """Carry scene generation request state and analyzed scene authority."""

    request: GenerationRequest
    behavior_snapshot: "EditorBehaviorSnapshot"
    scene_analysis: WorkflowSceneAnalysis


@dataclass(frozen=True, slots=True)
class SceneRunBookkeeping:
    """Apply scene-run bookkeeping through injected shell services."""

    workflows: Mapping[str, object] | None
    output_canvas_state_service: SceneOutputCanvasStateService | None
    output_scene_run_service: OutputSceneRunService | None

    def __call__(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...] = (),
    ) -> None:
        """Apply bookkeeping for a prepared scene generation run."""

        if self.workflows is None or self.output_canvas_state_service is None:
            raise AttributeError(
                "Scene output generation requires workflow and output canvas state "
                "services."
            )
        begin_output_generation_for_scene_run(
            workflows=self.workflows,
            output_canvas_state_service=self.output_canvas_state_service,
            output_scene_run_service=self.output_scene_run_service,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            scene_run_id=scene_run_id,
            scene_count=scene_count,
            snapshots=snapshots,
        )


class WorkspaceSceneGenerationActions:
    """Own shell prompt-scene generation queue actions."""

    def __init__(
        self,
        view: WorkspaceSceneGenerationActionView,
        *,
        build_bindings: Callable[[], SceneGenerationBindings],
        build_scene_snapshot: Callable[[str], GenerationJobSnapshot],
        preflight_error: SceneGenerationPreflightErrorFactory,
        preflight_error_type: type[Exception],
        preflight_failure: SceneGenerationPreflightFailureFactory,
    ) -> None:
        """Store prompt-scene queueing collaborators."""

        self._view = view
        self._build_bindings = build_bindings
        self._build_scene_snapshot = build_scene_snapshot
        self._preflight_error = preflight_error
        self._preflight_error_type = preflight_error_type
        self._preflight_failure = preflight_failure

    def enqueue_prompt_scene(self, scene_key: str) -> None:
        """Build and enqueue one generation snapshot for a prompt scene."""

        enqueue_prompt_scene_generation(
            scene_key=scene_key,
            queue_service=getattr(self._view, "generation_job_queue_service", None),
            feedback_dispatcher=self._view.generation_feedback_dispatcher,
            build_bindings=self._build_bindings,
            build_scene_snapshot=self._build_scene_snapshot,
            preflight_error=self._preflight_error,
            preflight_error_type=self._preflight_error_type,
            preflight_failure=self._preflight_failure,
        )


def scene_run_entries_from_snapshots(
    *,
    snapshots: Iterable[GenerationJobSnapshot],
    scene_count: int,
) -> tuple[tuple[str | None, str | None, int], ...]:
    """Return ordered scene-run entries from prepared scene snapshots."""

    return tuple(
        (
            snapshot.scene_key,
            snapshot.scene_title or snapshot.scene_key,
            scene_order,
        )
        for scene_order, snapshot in enumerate(
            sorted(
                (snapshot for snapshot in snapshots if snapshot.scene_key is not None),
                key=lambda snapshot: (
                    snapshot.scene_order
                    if snapshot.scene_order is not None
                    else scene_count
                ),
            )
        )
    )


def begin_output_generation_for_scene_run(
    *,
    workflows: Mapping[str, object],
    output_canvas_state_service: SceneOutputCanvasStateService,
    output_scene_run_service: OutputSceneRunService | None,
    workflow_id: str,
    workflow_name: str,
    scene_run_id: str,
    scene_count: int,
    snapshots: tuple[GenerationJobSnapshot, ...] = (),
) -> None:
    """Apply shell scene-run bookkeeping for a prepared scene generation run."""

    scenes = scene_run_entries_from_snapshots(
        snapshots=snapshots,
        scene_count=scene_count,
    )
    if output_scene_run_service is not None and scenes:
        output_scene_run_service.start_scene_run(
            scene_run_id=scene_run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            scenes=scenes,
        )
    output_canvas_state_service.begin_output_generation(
        workflows,
        workflow_id,
        scene_run_id=scene_run_id,
        scene_count=scene_count,
    )


def build_scene_generation_snapshots_from_context(
    *,
    context: SceneGenerationContext,
    preparation_service: SceneGenerationPreparationService,
    randomize_request_seeds: SceneGenerationSeedRandomizer,
    scene_run_bookkeeping: SceneRunBookkeepingCallback,
) -> tuple[GenerationJobSnapshot, ...]:
    """Capture immutable generation snapshots for every analyzed prompt scene."""

    request = context.request
    behavior_snapshot = context.behavior_snapshot
    randomize_request_seeds(request=request, behavior_snapshot=behavior_snapshot)
    result = preparation_service.prepare_scene_snapshots(
        request=CapturedGenerationRequest.capture(
            request=request,
            behavior_snapshot=behavior_snapshot,
        ),
        scene_analysis=context.scene_analysis,
    )
    if result.scene_run_id is not None and result.scene_count is not None:
        scene_run_bookkeeping(
            workflow_id=request.workflow_id,
            workflow_name=request.workflow_name,
            scene_run_id=result.scene_run_id,
            scene_count=result.scene_count,
            snapshots=result.snapshots,
        )
    return result.snapshots


def build_scene_generation_snapshot_from_context(
    *,
    context: SceneGenerationContext,
    scene_key: str,
    preparation_service: SceneGenerationPreparationService,
    randomize_request_seeds: SceneGenerationSeedRandomizer,
    preflight_error: SceneGenerationPreflightErrorFactory,
    scene_run_id_factory: Callable[[], str] | None = None,
) -> GenerationJobSnapshot:
    """Capture one immutable generation snapshot for one analyzed prompt scene."""

    request = context.request
    behavior_snapshot = context.behavior_snapshot
    scene_for_key(
        scene_analysis=context.scene_analysis,
        scene_key=scene_key,
        workflow_id=request.workflow_id,
        preflight_error=preflight_error,
    )
    randomize_request_seeds(request=request, behavior_snapshot=behavior_snapshot)
    return preparation_service.prepare_scene_snapshot(
        request=CapturedGenerationRequest.capture(
            request=request,
            behavior_snapshot=behavior_snapshot,
        ),
        scene_key=scene_key,
        scene_run_id=(scene_run_id_factory or _default_scene_run_id)(),
    )


def enqueue_prompt_scene_generation(
    *,
    scene_key: str,
    queue_service: object | None,
    feedback_dispatcher: SceneGenerationFeedbackDispatcher,
    build_bindings: Callable[[], SceneGenerationBindings],
    build_scene_snapshot: Callable[[str], GenerationJobSnapshot],
    preflight_error: SceneGenerationPreflightErrorFactory,
    preflight_error_type: type[Exception],
    preflight_failure: SceneGenerationPreflightFailureFactory,
) -> None:
    """Build callbacks and enqueue one prepared prompt-scene snapshot."""

    enqueue_snapshot = getattr(queue_service, "enqueue_snapshot", None)
    if not callable(enqueue_snapshot):
        error = preflight_error(
            workflow_id="queue",
            message=app_text("Queue this scene requires the generation queue."),
        )
        feedback_dispatcher.on_failure(
            preflight_failure(
                error,
                operation="queue_scene_generation",
                values={"scene_key": scene_key},
            )
        )
        return

    bindings = build_bindings()
    callbacks = generation_callbacks_from_scene_bindings(bindings)
    try:
        snapshot = build_scene_snapshot(scene_key)
    except preflight_error_type as error:
        callbacks.on_failure(
            preflight_failure(
                error,
                operation="generate_scene",
                values={"scene_key": scene_key},
            )
        )
        return
    enqueue_snapshot(snapshot, callbacks)


def generation_callbacks_from_scene_bindings(
    bindings: SceneGenerationBindings,
) -> GenerationCallbacks:
    """Return application generation callbacks from shell scene bindings."""

    return GenerationCallbacks(
        randomize_seeds=bindings.randomize_seeds,
        clear_output=bindings.clear_output_for_workflow,
        on_run_started=bindings.on_run_started,
        on_progress=bindings.on_progress,
        on_model_load_progress=bindings.on_model_load_progress,
        on_preview=bindings.on_preview,
        on_output_image=bindings.on_output_image,
        on_failure=bindings.on_failure,
        on_timing=bindings.on_timing,
        on_completed=bindings.on_completed,
    )


def scene_generation_context(
    *,
    request: GenerationRequest,
    behavior_snapshot: "EditorBehaviorSnapshot | None",
    preflight_error: SceneGenerationPreflightErrorFactory,
) -> SceneGenerationContext:
    """Return generation request, prompt index, and scene analysis."""

    if behavior_snapshot is None:
        raise preflight_error(
            workflow_id=request.workflow_id,
            message=app_text(
                "Scene generation requires an active workflow prompt index."
            ),
        )

    scene_analysis = PromptSceneAnalysisService().analyze(
        workflow=cast(Any, request.workflow),
        endpoint_index=behavior_snapshot.prompt_endpoint_index,
    )
    if not scene_analysis.can_generate_scenes:
        raise preflight_error(
            workflow_id=request.workflow_id,
            message=(
                app_text(
                    "Scene generation requires at least one **scene marker in the "
                    "first positive prompt."
                )
            ),
        )

    return SceneGenerationContext(
        request=request,
        behavior_snapshot=behavior_snapshot,
        scene_analysis=scene_analysis,
    )


def scene_for_key(
    *,
    scene_analysis: WorkflowSceneAnalysis,
    scene_key: str,
    workflow_id: str,
    preflight_error: SceneGenerationPreflightErrorFactory,
) -> WorkflowScene:
    """Return one runnable scene by key or raise a preflight error."""

    for scene in scene_analysis.scenes:
        if scene.key == scene_key:
            return scene
    raise preflight_error(
        workflow_id=workflow_id,
        message=translate_application_message(
            "Generate scene could not find runnable scene: %1",
            scene_key,
        ),
    )


def _default_scene_run_id() -> str:
    """Return an opaque scene-run id for one selected prompt scene."""

    return uuid4().hex


__all__ = [
    "begin_output_generation_for_scene_run",
    "build_scene_generation_snapshot_from_context",
    "build_scene_generation_snapshots_from_context",
    "enqueue_prompt_scene_generation",
    "generation_callbacks_from_scene_bindings",
    "OutputSceneRunService",
    "SceneGenerationBindings",
    "SceneOutputCanvasStateService",
    "SceneGenerationContext",
    "SceneGenerationFeedbackDispatcher",
    "SceneGenerationPreparationService",
    "SceneGenerationPreflightErrorFactory",
    "SceneGenerationPreflightFailureFactory",
    "SceneGenerationQueueService",
    "SceneGenerationSeedRandomizer",
    "SceneRunBookkeeping",
    "SceneRunBookkeepingCallback",
    "WorkspaceSceneGenerationActions",
    "WorkspaceSceneGenerationActionView",
    "scene_for_key",
    "scene_generation_context",
    "scene_run_entries_from_snapshots",
]
