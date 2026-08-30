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

"""Tests for shell generation snapshot-building helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.application.generation import (
    CapturedGenerationRequest,
    GenerationJobSnapshot,
    GenerationPreparationResult,
    GenerationRequest,
)
from substitute.application.recipes.recipe_io_service import WorkflowLike
from substitute.presentation.shell.workspace_generation_snapshot_builder import (
    capture_queued_snapshot_preparation,
)


from tests.presentation.shell.generation.snapshot_builder.support import (
    _behavior_snapshot,
    _workflow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_snapshot_builder.py"
)
WORKSPACE_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "workspace_controller.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
    "substitute.presentation.shell.workspace_generation_controller",
)


def test_capture_queued_snapshot_preparation_uses_detached_request() -> None:
    """Queued preparation should capture workflow state before task execution."""

    workflow = SimpleNamespace(seed="before")
    captured_workflows: list[object] = []
    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A",
        sugar_script_text="# sugar",
    )

    class _PreparationService:
        """Record the detached request used by queued preparation."""

        def prepare_queued_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
        ) -> GenerationPreparationResult:
            """Record captured workflow state and return a snapshot result."""

            captured_workflows.append(request.workflow)
            return GenerationPreparationResult(snapshots=(snapshot,))

    def _ignore_scene_run(
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...],
    ) -> None:
        """Ignore scene-run callbacks for the no-scene case."""

        _ = workflow_id, workflow_name, scene_run_id, scene_count, snapshots

    preparation = capture_queued_snapshot_preparation(
        request=GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            workflow=cast(WorkflowLike, workflow),
        ),
        behavior_snapshot=None,
        preparation_service=_PreparationService(),
        on_scene_run_prepared=_ignore_scene_run,
    )

    workflow.seed = "after"
    result = preparation.prepare_snapshots()

    assert result.snapshots == (snapshot,)
    assert len(captured_workflows) == 1
    assert captured_workflows[0] is not workflow
    assert getattr(captured_workflows[0], "seed") == "before"
    assert preparation.on_prepared(result) == (snapshot,)


def test_capture_queued_snapshot_preparation_applies_scene_run_bookkeeping() -> None:
    """Prepared scene metadata should flow through the injected scene callback."""

    snapshot = GenerationJobSnapshot(
        workflow_id="workflow-a",
        workflow_name="Recipe A - Scene",
        sugar_script_text="# scene",
        scene_run_id="scene-run-a",
        scene_key="scene-a",
        scene_count=2,
    )
    scene_calls: list[tuple[str, str, str, int, tuple[GenerationJobSnapshot, ...]]] = []
    result = GenerationPreparationResult(
        snapshots=(snapshot,),
        scene_run_id="scene-run-a",
        scene_count=2,
    )

    class _PreparationService:
        """Return a prebuilt scene preparation result."""

        def prepare_queued_snapshots(
            self,
            *,
            request: CapturedGenerationRequest,
        ) -> GenerationPreparationResult:
            """Return the scene preparation result."""

            _ = request
            return result

    def _record_scene_run(
        *,
        workflow_id: str,
        workflow_name: str,
        scene_run_id: str,
        scene_count: int,
        snapshots: tuple[GenerationJobSnapshot, ...],
    ) -> None:
        """Record scene-run bookkeeping callback arguments."""

        scene_calls.append(
            (
                workflow_id,
                workflow_name,
                scene_run_id,
                scene_count,
                snapshots,
            )
        )

    preparation = capture_queued_snapshot_preparation(
        request=GenerationRequest(
            workflow_id="workflow-a",
            workflow_name="Recipe A",
            workflow=cast(WorkflowLike, _workflow()),
        ),
        behavior_snapshot=_behavior_snapshot(),
        preparation_service=_PreparationService(),
        on_scene_run_prepared=_record_scene_run,
    )

    assert preparation.prepare_snapshots() is result
    assert preparation.on_prepared(result) == (snapshot,)
    assert scene_calls == [
        (
            "workflow-a",
            "Recipe A",
            "scene-run-a",
            2,
            (snapshot,),
        )
    ]
