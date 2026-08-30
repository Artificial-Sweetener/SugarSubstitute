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

import pytest

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
    SeedRandomizationResult,
)
from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.presentation.shell.workspace_scene_generation_controller import (
    build_scene_generation_snapshot_from_context,
    build_scene_generation_snapshots_from_context,
    scene_generation_context,
)


from tests.presentation.shell.generation.scenes.support import (
    _ScenePreflightError,
    _preflight_error,
    _workflow,
    _behavior_snapshot,
    _request,
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
    ) -> SeedRandomizationResult:
        """Record randomization and mutate the live workflow before capture."""

        randomized.append((request, behavior_snapshot))
        setattr(request.workflow, "randomized_marker", "after-randomization")
        return SeedRandomizationResult()

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
    ) -> SeedRandomizationResult:
        """Record seed randomization."""

        assert behavior_snapshot is context.behavior_snapshot
        randomize_calls.append(request)
        return SeedRandomizationResult()

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
    ) -> SeedRandomizationResult:
        """Record unexpected randomization."""

        nonlocal randomize_calls
        randomize_calls += 1
        return SeedRandomizationResult()

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
