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

"""Tests for shell prompt-scene generation helpers."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationCallbacks,
    GenerationFailure,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.recipes.recipe_io_service import WorkflowLike
from substitute.domain.links.prompt_endpoints import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.presentation.shell.workspace_scene_generation_controller import (
    SceneGenerationBindings,
    SceneGenerationFeedbackDispatcher,
    SceneGenerationPreflightFailureFactory,
    WorkspaceSceneGenerationActions,
    begin_output_generation_for_scene_run,
    build_scene_generation_snapshot_from_context,
    build_scene_generation_snapshots_from_context,
    enqueue_prompt_scene_generation,
    scene_for_key,
    scene_generation_context,
    scene_run_entries_from_snapshots,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_scene_generation_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


class _ScenePreflightError(RuntimeError):
    """Test preflight error carrying workflow context."""

    def __init__(self, *, workflow_id: str, message: str) -> None:
        """Store workflow failure context."""

        super().__init__(message)
        self.workflow_id = workflow_id
        self.message = message


def _preflight_error(*, workflow_id: str, message: str) -> _ScenePreflightError:
    """Return a test scene preflight exception."""

    return _ScenePreflightError(workflow_id=workflow_id, message=message)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _workflow(prompt_text: str) -> SimpleNamespace:
    """Return a workflow-like object with one positive prompt endpoint."""

    return SimpleNamespace(
        stack_order=["Text"],
        cubes={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {"inputs": {"prompt_template": prompt_text}},
                    }
                }
            )
        },
    )


def _behavior_snapshot() -> EditorBehaviorSnapshot:
    """Return a behavior snapshot with one positive prompt endpoint."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
        prompt_endpoint_index=PromptEndpointIndex.from_endpoints(
            (
                PromptEndpoint(
                    cube_alias="Text",
                    role=PromptRole.POSITIVE,
                    node_name="positive_prompt",
                    field_key="prompt_template",
                ),
            )
        ),
    )


def _request(workflow: object) -> GenerationRequest:
    """Return a generation request for scene helper tests."""

    return GenerationRequest(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        workflow=cast(WorkflowLike, workflow),
    )


def _scene_bindings(failures: list[GenerationFailure]) -> SceneGenerationBindings:
    """Return generation bindings for prompt-scene enqueue tests."""

    return cast(
        SceneGenerationBindings,
        SimpleNamespace(
            randomize_seeds=lambda: None,
            clear_output_for_workflow=lambda _workflow_id: None,
            on_run_started=lambda _event: None,
            on_progress=lambda _progress: None,
            on_model_load_progress=lambda _progress: None,
            on_preview=lambda _preview: None,
            on_output_image=lambda _output: None,
            on_failure=failures.append,
            on_timing=lambda _timing: None,
            on_completed=lambda _event: None,
        ),
    )


def test_scene_generation_context_analyzes_runnable_scenes() -> None:
    """Scene context construction should analyze prompt scene authority."""

    context = scene_generation_context(
        request=_request(
            _workflow("quality\n\n**portrait\nstudio portrait\n\n**cafe\nat cafe")
        ),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )

    assert context.request.workflow_id == "workflow-a"
    assert context.behavior_snapshot is not None
    assert [
        (scene.key, scene.title, scene.order) for scene in context.scene_analysis.scenes
    ] == [
        ("portrait", "portrait", 0),
        ("cafe", "cafe", 1),
    ]


def test_scene_generation_context_requires_behavior_snapshot() -> None:
    """Scene generation should fail without prompt endpoint metadata."""

    with pytest.raises(_ScenePreflightError) as raised:
        scene_generation_context(
            request=_request(_workflow("**portrait\nstudio portrait")),
            behavior_snapshot=None,
            preflight_error=_preflight_error,
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Scene generation requires an active workflow prompt index."
    )


def test_scene_generation_context_requires_scene_markers() -> None:
    """Scene generation should fail when no runnable authority scenes exist."""

    with pytest.raises(_ScenePreflightError) as raised:
        scene_generation_context(
            request=_request(_workflow("quality portrait")),
            behavior_snapshot=_behavior_snapshot(),
            preflight_error=_preflight_error,
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Scene generation requires at least one **scene marker in the "
        "first positive prompt."
    )


def test_scene_for_key_returns_matching_scene() -> None:
    """Scene lookup should return a runnable scene by key."""

    context = scene_generation_context(
        request=_request(_workflow("**portrait\nstudio\n\n**cafe\ncoffee")),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )

    scene = scene_for_key(
        scene_analysis=context.scene_analysis,
        scene_key="cafe",
        workflow_id="workflow-a",
        preflight_error=_preflight_error,
    )

    assert scene.key == "cafe"
    assert scene.order == 1


def test_scene_for_key_reports_unknown_scene() -> None:
    """Scene lookup should fail through the injected preflight error factory."""

    context = scene_generation_context(
        request=_request(_workflow("**portrait\nstudio")),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )

    with pytest.raises(_ScenePreflightError) as raised:
        scene_for_key(
            scene_analysis=context.scene_analysis,
            scene_key="missing",
            workflow_id="workflow-a",
            preflight_error=_preflight_error,
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Generate scene could not find runnable scene: missing"
    )


def test_build_scene_generation_snapshots_from_context_prepares_and_tracks_run() -> (
    None
):
    """Multi-scene snapshot capture should randomize before preparation."""

    workflow = _workflow("**portrait\nstudio\n\n**cafe\ncoffee")
    context = scene_generation_context(
        request=_request(workflow),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )
    snapshots = (
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - portrait",
            sugar_script_text="# portrait",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - cafe",
            sugar_script_text="# cafe",
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
        ),
    )

    class _PreparationService:
        """Record multi-scene preparation inputs."""

        captured_request: CapturedGenerationRequest | None = None
        captured_scene_analysis: object | None = None

        def prepare_scene_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
            scene_analysis: object | None = None,
            scene_run_id: str | None = None,
        ) -> GenerationPreparationResult:
            """Return prepared scene snapshots."""

            self.captured_request = request
            self.captured_scene_analysis = scene_analysis
            assert scene_run_id is None
            return GenerationPreparationResult(
                snapshots=snapshots,
                scene_run_id="scene-run-a",
                scene_count=2,
            )

        def prepare_scene_snapshot(
            self,
            *,
            request: CapturedGenerationRequest,
            scene_key: str,
            scene_run_id: str | None = None,
        ) -> GenerationJobSnapshot:
            """Fail if single-scene preparation is requested."""

            raise AssertionError("single scene preparation should not run")

    randomized: list[tuple[GenerationRequest, EditorBehaviorSnapshot | None]] = []
    bookkeeping_calls: list[dict[str, object]] = []
    service = _PreparationService()

    def _randomize(
        *,
        request: GenerationRequest,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Record randomization and mutate the live workflow before capture."""

        randomized.append((request, behavior_snapshot))
        setattr(request.workflow, "randomized_marker", "after-randomization")

    def _bookkeeping(**values: object) -> None:
        """Record scene-run bookkeeping values."""

        bookkeeping_calls.append(values)

    result = build_scene_generation_snapshots_from_context(
        context=context,
        preparation_service=service,
        randomize_request_seeds=_randomize,
        scene_run_bookkeeping=_bookkeeping,
    )

    assert result == snapshots
    assert randomized == [(context.request, context.behavior_snapshot)]
    assert service.captured_request is not None
    assert service.captured_request.workflow is not workflow
    assert service.captured_request.workflow.randomized_marker == (
        "after-randomization"
    )
    assert service.captured_scene_analysis is context.scene_analysis
    assert bookkeeping_calls == [
        {
            "workflow_id": "workflow-a",
            "workflow_name": "Recipe A",
            "scene_run_id": "scene-run-a",
            "scene_count": 2,
            "snapshots": snapshots,
        }
    ]


def test_build_scene_generation_snapshot_from_context_validates_and_prepares_scene() -> (
    None
):
    """Single-scene snapshot capture should validate keys before preparation."""

    context = scene_generation_context(
        request=_request(_workflow("**portrait\nstudio\n\n**cafe\ncoffee")),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )
    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A - cafe",
        sugar_script_text="# cafe",
        scene_key="cafe",
        scene_title="Cafe",
        scene_order=1,
    )

    class _PreparationService:
        """Record single-scene preparation inputs."""

        captured_request: CapturedGenerationRequest | None = None
        captured_scene_key: str | None = None
        captured_scene_run_id: str | None = None

        def prepare_scene_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
            scene_analysis: object | None = None,
            scene_run_id: str | None = None,
        ) -> GenerationPreparationResult:
            """Fail if multi-scene preparation is requested."""

            raise AssertionError("multi-scene preparation should not run")

        def prepare_scene_snapshot(
            self,
            *,
            request: CapturedGenerationRequest,
            scene_key: str,
            scene_run_id: str | None = None,
        ) -> GenerationJobSnapshot:
            """Return the selected scene snapshot."""

            self.captured_request = request
            self.captured_scene_key = scene_key
            self.captured_scene_run_id = scene_run_id
            return snapshot

    randomize_calls: list[GenerationRequest] = []
    service = _PreparationService()

    def _randomize(
        *,
        request: GenerationRequest,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Record seed randomization."""

        assert behavior_snapshot is context.behavior_snapshot
        randomize_calls.append(request)

    result = build_scene_generation_snapshot_from_context(
        context=context,
        scene_key="cafe",
        preparation_service=service,
        randomize_request_seeds=_randomize,
        preflight_error=_preflight_error,
        scene_run_id_factory=lambda: "scene-run-single",
    )

    assert result == snapshot
    assert randomize_calls == [context.request]
    assert service.captured_request is not None
    assert service.captured_scene_key == "cafe"
    assert service.captured_scene_run_id == "scene-run-single"


def test_build_scene_generation_snapshot_from_context_rejects_unknown_scene_first() -> (
    None
):
    """Unknown scene keys should fail before randomization or preparation."""

    context = scene_generation_context(
        request=_request(_workflow("**portrait\nstudio")),
        behavior_snapshot=_behavior_snapshot(),
        preflight_error=_preflight_error,
    )
    randomize_calls = 0
    preparation_calls = 0

    class _PreparationService:
        """Record any unexpected preparation calls."""

        def prepare_scene_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
            scene_analysis: object | None = None,
            scene_run_id: str | None = None,
        ) -> GenerationPreparationResult:
            """Fail if multi-scene preparation is requested."""

            raise AssertionError("multi-scene preparation should not run")

        def prepare_scene_snapshot(
            self,
            *,
            request: CapturedGenerationRequest,
            scene_key: str,
            scene_run_id: str | None = None,
        ) -> GenerationJobSnapshot:
            """Record unexpected single-scene preparation."""

            nonlocal preparation_calls
            preparation_calls += 1
            raise AssertionError("single scene preparation should not run")

    def _randomize(
        *,
        request: GenerationRequest,
        behavior_snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Record unexpected randomization."""

        nonlocal randomize_calls
        randomize_calls += 1

    with pytest.raises(_ScenePreflightError) as raised:
        build_scene_generation_snapshot_from_context(
            context=context,
            scene_key="missing",
            preparation_service=_PreparationService(),
            randomize_request_seeds=_randomize,
            preflight_error=_preflight_error,
            scene_run_id_factory=lambda: "scene-run-single",
        )

    assert raised.value.workflow_id == "workflow-a"
    assert raised.value.message == (
        "Generate scene could not find runnable scene: missing"
    )
    assert randomize_calls == 0
    assert preparation_calls == 0


def test_enqueue_prompt_scene_generation_enqueues_single_snapshot() -> None:
    """Prompt-scene enqueueing should queue one prepared scene snapshot."""

    failures: list[GenerationFailure] = []
    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A - portrait",
        sugar_script_text="# portrait",
        scene_key="portrait",
    )
    enqueued: list[tuple[GenerationJobSnapshot, GenerationCallbacks]] = []
    built_scene_keys: list[str] = []
    feedback_failures: list[GenerationFailure] = []

    class _QueueService:
        """Record enqueued scene snapshots."""

        def enqueue_snapshot(
            self,
            snapshot_arg: GenerationJobSnapshot,
            callbacks: GenerationCallbacks,
        ) -> None:
            """Record enqueue arguments."""

            enqueued.append((snapshot_arg, callbacks))

    def _build_scene_snapshot(scene_key: str) -> GenerationJobSnapshot:
        """Return one prepared snapshot and record the selected scene."""

        built_scene_keys.append(scene_key)
        return snapshot

    enqueue_prompt_scene_generation(
        scene_key="portrait",
        queue_service=_QueueService(),
        feedback_dispatcher=cast(
            SceneGenerationFeedbackDispatcher,
            SimpleNamespace(on_failure=feedback_failures.append),
        ),
        build_bindings=lambda: _scene_bindings(failures),
        build_scene_snapshot=_build_scene_snapshot,
        preflight_error=_preflight_error,
        preflight_error_type=_ScenePreflightError,
        preflight_failure=cast(
            SceneGenerationPreflightFailureFactory,
            _generation_failure_from_preflight,
        ),
    )

    assert built_scene_keys == ["portrait"]
    assert len(enqueued) == 1
    assert enqueued[0][0] is snapshot
    assert isinstance(enqueued[0][1], GenerationCallbacks)
    enqueued[0][1].on_failure(
        GenerationFailure(
            stage="runtime",
            workflow_id="workflow-a",
            message="runtime failure",
        )
    )
    assert [failure.message for failure in failures] == ["runtime failure"]
    assert feedback_failures == []


def test_workspace_scene_generation_actions_enqueues_through_view_queue() -> None:
    """Scene generation actions should route through composed view collaborators."""

    failures: list[GenerationFailure] = []
    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A - portrait",
        sugar_script_text="# portrait",
        scene_key="portrait",
    )
    enqueued: list[tuple[GenerationJobSnapshot, GenerationCallbacks]] = []
    built_scene_keys: list[str] = []
    feedback_failures: list[GenerationFailure] = []

    class _QueueService:
        """Record enqueued scene snapshots."""

        def enqueue_snapshot(
            self,
            snapshot_arg: GenerationJobSnapshot,
            callbacks: GenerationCallbacks,
        ) -> None:
            """Record enqueue arguments."""

            enqueued.append((snapshot_arg, callbacks))

    def _build_scene_snapshot(scene_key: str) -> GenerationJobSnapshot:
        """Return one prepared snapshot and record the selected scene."""

        built_scene_keys.append(scene_key)
        return snapshot

    view = SimpleNamespace(
        generation_job_queue_service=_QueueService(),
        generation_feedback_dispatcher=SimpleNamespace(
            on_failure=feedback_failures.append
        ),
    )
    actions = WorkspaceSceneGenerationActions(
        cast(Any, view),
        build_bindings=lambda: _scene_bindings(failures),
        build_scene_snapshot=_build_scene_snapshot,
        preflight_error=_preflight_error,
        preflight_error_type=_ScenePreflightError,
        preflight_failure=cast(
            SceneGenerationPreflightFailureFactory,
            _generation_failure_from_preflight,
        ),
    )

    actions.enqueue_prompt_scene("portrait")

    assert built_scene_keys == ["portrait"]
    assert len(enqueued) == 1
    assert enqueued[0][0] is snapshot
    assert isinstance(enqueued[0][1], GenerationCallbacks)
    assert failures == []
    assert feedback_failures == []


def test_enqueue_prompt_scene_generation_reports_unknown_scene_without_enqueue() -> (
    None
):
    """Unknown scene keys should fail through generation callbacks."""

    callback_failures: list[GenerationFailure] = []
    feedback_failures: list[GenerationFailure] = []
    enqueued: list[object] = []
    failure_calls: list[tuple[str, str, dict[str, object] | None]] = []

    class _QueueService:
        """Record unexpected enqueue calls."""

        def enqueue_snapshot(
            self,
            snapshot: GenerationJobSnapshot,
            callbacks: GenerationCallbacks,
        ) -> None:
            """Record enqueue arguments."""

            enqueued.append((snapshot, callbacks))

    def _build_scene_snapshot(scene_key: str) -> GenerationJobSnapshot:
        """Raise the scene preflight error for an unknown scene."""

        raise _ScenePreflightError(
            workflow_id="workflow-a",
            message=f"Generate scene could not find runnable scene: {scene_key}",
        )

    def _preflight_failure(
        error_value: object,
        *,
        operation: str,
        values: dict[str, object] | None = None,
    ) -> GenerationFailure:
        """Record preflight failure conversion."""

        error = cast(_ScenePreflightError, error_value)
        failure_calls.append((error.workflow_id, operation, values))
        return GenerationFailure(
            stage="preflight",
            workflow_id=error.workflow_id,
            message=error.message,
        )

    enqueue_prompt_scene_generation(
        scene_key="missing",
        queue_service=_QueueService(),
        feedback_dispatcher=cast(
            SceneGenerationFeedbackDispatcher,
            SimpleNamespace(on_failure=feedback_failures.append),
        ),
        build_bindings=lambda: _scene_bindings(callback_failures),
        build_scene_snapshot=_build_scene_snapshot,
        preflight_error=_preflight_error,
        preflight_error_type=_ScenePreflightError,
        preflight_failure=cast(
            SceneGenerationPreflightFailureFactory,
            _preflight_failure,
        ),
    )

    assert enqueued == []
    assert feedback_failures == []
    assert [
        (failure.stage, failure.workflow_id, failure.message)
        for failure in callback_failures
    ] == [
        (
            "preflight",
            "workflow-a",
            "Generate scene could not find runnable scene: missing",
        )
    ]
    assert failure_calls == [("workflow-a", "generate_scene", {"scene_key": "missing"})]


def test_enqueue_prompt_scene_generation_reports_missing_queue_without_bindings() -> (
    None
):
    """Missing queue service should fail before callbacks or snapshot building."""

    feedback_failures: list[GenerationFailure] = []
    binding_builds = 0
    snapshot_builds = 0
    failure_calls: list[tuple[str, str, dict[str, object] | None]] = []

    def _build_bindings() -> SceneGenerationBindings:
        """Record unexpected binding construction."""

        nonlocal binding_builds
        binding_builds += 1
        return _scene_bindings([])

    def _build_scene_snapshot(scene_key: str) -> GenerationJobSnapshot:
        """Record unexpected snapshot construction."""

        nonlocal snapshot_builds
        snapshot_builds += 1
        raise AssertionError("snapshot should not be built without a queue")

    def _preflight_failure(
        error_value: object,
        *,
        operation: str,
        values: dict[str, object] | None = None,
    ) -> GenerationFailure:
        """Record queue preflight failure conversion."""

        error = cast(_ScenePreflightError, error_value)
        failure_calls.append((error.workflow_id, operation, values))
        return GenerationFailure(
            stage="preflight",
            workflow_id=error.workflow_id,
            message=error.message,
        )

    enqueue_prompt_scene_generation(
        scene_key="portrait",
        queue_service=None,
        feedback_dispatcher=cast(
            SceneGenerationFeedbackDispatcher,
            SimpleNamespace(on_failure=feedback_failures.append),
        ),
        build_bindings=_build_bindings,
        build_scene_snapshot=_build_scene_snapshot,
        preflight_error=_preflight_error,
        preflight_error_type=_ScenePreflightError,
        preflight_failure=cast(
            SceneGenerationPreflightFailureFactory,
            _preflight_failure,
        ),
    )

    assert binding_builds == 0
    assert snapshot_builds == 0
    assert [
        (failure.stage, failure.workflow_id, failure.message)
        for failure in feedback_failures
    ] == [
        (
            "preflight",
            "queue",
            "Queue this scene requires the generation queue.",
        )
    ]
    assert failure_calls == [
        ("queue", "queue_scene_generation", {"scene_key": "portrait"})
    ]


def _generation_failure_from_preflight(
    error_value: object,
    *,
    operation: str,
    values: dict[str, object] | None = None,
) -> GenerationFailure:
    """Return a generation failure from a test preflight exception."""

    _ = operation, values
    error = cast(_ScenePreflightError, error_value)
    return GenerationFailure(
        stage="preflight",
        workflow_id=error.workflow_id,
        message=error.message,
    )


def test_scene_run_entries_from_snapshots_orders_scene_metadata() -> None:
    """Scene-run entries should follow snapshot scene order with fallback ordering."""

    snapshots = (
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - later",
            sugar_script_text="# later",
            scene_key="later",
            scene_title="Later",
            scene_order=3,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - missing-order",
            sugar_script_text="# missing",
            scene_key="missing-order",
            scene_title=None,
            scene_order=None,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - first",
            sugar_script_text="# first",
            scene_key="first",
            scene_title="First",
            scene_order=0,
        ),
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            sugar_script_text="# no scene",
        ),
    )

    assert scene_run_entries_from_snapshots(
        snapshots=snapshots,
        scene_count=4,
    ) == (
        ("first", "First", 0),
        ("later", "Later", 1),
        ("missing-order", "missing-order", 2),
    )


def test_begin_output_generation_for_scene_run_updates_scene_services() -> None:
    """Scene-run bookkeeping should update scene navigation before canvas state."""

    workflows = {"workflow-a": object()}
    calls: list[tuple[str, object]] = []
    snapshots = (
        GenerationJobSnapshot(
            workflow_id="workflow-a",
            workflow_name="Recipe A - portrait",
            sugar_script_text="# portrait",
            scene_run_id="scene-run-a",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
        ),
    )

    class _SceneRunService:
        """Record scene-run navigation metadata."""

        def start_scene_run(
            self,
            *,
            scene_run_id: str,
            workflow_id: str,
            workflow_name: str,
            scenes: object,
        ) -> None:
            """Record scene-run start arguments."""

            calls.append(
                (
                    "scene_run",
                    {
                        "scene_run_id": scene_run_id,
                        "workflow_id": workflow_id,
                        "workflow_name": workflow_name,
                        "scenes": scenes,
                    },
                )
            )

    class _OutputCanvasStateService:
        """Record output canvas generation state."""

        def begin_output_generation(
            self,
            workflows_arg: object,
            workflow_id: str,
            *,
            scene_run_id: str | None = None,
            scene_count: int | None = None,
        ) -> None:
            """Record output generation arguments."""

            calls.append(
                (
                    "output_canvas",
                    {
                        "workflows": workflows_arg,
                        "workflow_id": workflow_id,
                        "scene_run_id": scene_run_id,
                        "scene_count": scene_count,
                    },
                )
            )

    begin_output_generation_for_scene_run(
        workflows=workflows,
        output_canvas_state_service=_OutputCanvasStateService(),
        output_scene_run_service=_SceneRunService(),
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        scene_run_id="scene-run-a",
        scene_count=1,
        snapshots=snapshots,
    )

    assert calls == [
        (
            "scene_run",
            {
                "scene_run_id": "scene-run-a",
                "workflow_id": "workflow-a",
                "workflow_name": "Recipe A",
                "scenes": (("portrait", "Portrait", 0),),
            },
        ),
        (
            "output_canvas",
            {
                "workflows": workflows,
                "workflow_id": "workflow-a",
                "scene_run_id": "scene-run-a",
                "scene_count": 1,
            },
        ),
    ]


def test_begin_output_generation_for_scene_run_tolerates_missing_scene_service() -> (
    None
):
    """Output canvas generation state should update without scene-run navigation."""

    calls: list[tuple[object, str, str | None, int | None]] = []

    class _OutputCanvasStateService:
        """Record output canvas generation state."""

        def begin_output_generation(
            self,
            workflows: object,
            workflow_id: str,
            *,
            scene_run_id: str | None = None,
            scene_count: int | None = None,
        ) -> None:
            """Record output generation arguments."""

            calls.append((workflows, workflow_id, scene_run_id, scene_count))

    workflows = {"workflow-a": object()}
    begin_output_generation_for_scene_run(
        workflows=workflows,
        output_canvas_state_service=_OutputCanvasStateService(),
        output_scene_run_service=None,
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        scene_run_id="scene-run-a",
        scene_count=2,
    )

    assert calls == [(workflows, "workflow-a", "scene-run-a", 2)]


def test_workspace_scene_generation_controller_imports_no_concrete_boundaries() -> None:
    """Scene generation helpers should not import Qt or concrete controllers."""

    forbidden_imports = tuple(
        sorted(
            imported_module
            for imported_module in _imported_module_names(SOURCE_PATH)
            if imported_module.startswith(FORBIDDEN_IMPORT_PREFIXES)
        )
    )

    assert forbidden_imports == ()
