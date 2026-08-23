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

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast


from substitute.application.generation import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationJobSnapshot,
)
from substitute.presentation.shell.workspace_scene_generation_controller import (
    SceneGenerationBindings,
    SceneGenerationFeedbackDispatcher,
    SceneGenerationPreflightFailureFactory,
    WorkspaceSceneGenerationActions,
    enqueue_prompt_scene_generation,
)


from tests.presentation.shell.generation.scenes.support import (
    _ScenePreflightError,
    _preflight_error,
    _scene_bindings,
    _generation_failure_from_preflight,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
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
