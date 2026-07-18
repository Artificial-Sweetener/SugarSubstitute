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

"""Tests for generation job result snapshot construction."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from substitute.application.generation import GenerationResultSnapshotService
from substitute.domain.generation import (
    GenerationJobOutputRecord,
    GenerationJobSnapshot,
    GenerationQueueJob,
    SeedControlState,
    SeedMode,
)
from substitute.domain.recipes.sugar_ast import ParsedSugarScript
from substitute.domain.workflow import OutputFocusMode
from substitute.domain.common import JsonObject
from substitute.domain.comfy_workflow import (
    DirectWorkflowGenerationPlan,
    DirectWorkflowOutputManifest,
)


def test_generation_result_snapshot_service_builds_workspace_with_outputs() -> None:
    """Live job replay should carry workflow state and output image references."""

    job = _job("job-1")
    outputs = (
        _output(
            "job-1",
            sequence=1,
            path=Path("first.png"),
            metadata={"list_index": 0},
        ),
        _output(
            "job-1",
            sequence=2,
            path=Path("second.png"),
            scene_count=2,
            metadata={"list_index": 1},
        ),
    )
    service = GenerationResultSnapshotService(
        live_results=_LiveResults(job=job, outputs=outputs),
        recipe_parser=_RecipeParser(),
    )

    result = service.build_for_live_job("job-1")

    assert result.warnings == ()
    assert result.snapshot is not None
    workspace = result.snapshot.workspace
    workflow_snapshot = workspace.workflows[0]
    workflow = workflow_snapshot.workflow
    assert workflow_snapshot.workflow_id == "job-job-1"
    assert workflow_snapshot.tab_label == "Portrait Workflow"
    assert workflow.stack_order == ["Base"]
    assert workflow.cubes["Base"].cube_id == "cube.load"
    assert workflow.global_overrides == {"seed": {"value": 1234}}
    assert (
        workflow.cubes["Base"].field_control_states["ksampler"]["seed"].mode
        == SeedMode.FIXED
    )
    assert workflow.override_control_states["seed"].mode == SeedMode.FIXED
    assert workflow.global_override_selections == {"seed": True}
    assert len(workflow_snapshot.output_images) == 2
    assert [ref.sequence for ref in workflow_snapshot.output_images] == [1, 2]
    assert [ref.metadata.list_index for ref in workflow_snapshot.output_images] == [
        0,
        1,
    ]
    assert [ref.metadata.node_id for ref in workflow_snapshot.output_images] == [
        "12",
        "12",
    ]
    assert [
        ref.metadata.generation_run_id for ref in workflow_snapshot.output_images
    ] == ["job-1", "job-1"]
    assert workflow.output_image_uuids == [
        UUID(ref.image_id) for ref in workflow_snapshot.output_images
    ]
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == workflow.output_image_uuids[-1]
    assert workflow.active_output_scene_overview is True
    assert workflow.active_output_source_key is None
    assert workflow.active_output_scene_key is None


def test_generation_result_snapshot_service_reports_missing_job() -> None:
    """Missing live job should return a warning instead of a snapshot."""

    service = GenerationResultSnapshotService(
        live_results=_LiveResults(job=None, outputs=()),
        recipe_parser=_RecipeParser(),
    )

    result = service.build_for_live_job("missing")

    assert result.snapshot is None
    assert result.warnings == ("Generation job missing was not found.",)


def test_generation_result_snapshot_service_restores_direct_graph_without_sugar() -> (
    None
):
    """Direct generation replay should reconstruct the unified editor document."""

    graph: JsonObject = {
        "8": {"class_type": "KSampler", "inputs": {"seed": 321}},
    }
    job = GenerationQueueJob(
        job_id="job-direct",
        snapshot=GenerationJobSnapshot(
            workflow_id="workflow-direct",
            workflow_name="Direct Workflow",
            sugar_script_text="",
            direct_workflow_plan=DirectWorkflowGenerationPlan(
                authored_api_graph=graph,
                output_manifest=DirectWorkflowOutputManifest(
                    sources=(),
                    hijacked_sink_node_ids=frozenset(),
                    preserved_output_node_ids=(),
                ),
            ),
        ),
        created_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        status="completed",
    )
    service = GenerationResultSnapshotService(
        live_results=_LiveResults(job=job, outputs=()),
        recipe_parser=_FailingRecipeParser(),
    )

    result = service.build_for_live_job("job-direct")

    assert result.snapshot is not None
    workflow = result.snapshot.workspace.workflows[0].workflow
    assert workflow.direct_workflow is not None
    assert workflow.direct_workflow.buffer == {"nodes": graph}
    assert workflow.cubes == {}


class _FailingRecipeParser:
    """Fail if direct result replay incorrectly enters Sugar parsing."""

    def parse_recipe_script(self, sugar_script_text: str) -> ParsedSugarScript:
        """Reject every unexpected recipe parse call."""

        raise AssertionError(f"Unexpected Sugar parse: {sugar_script_text!r}")


class _LiveResults:
    """Fake current-session result lookup for snapshot tests."""

    def __init__(
        self,
        *,
        job: GenerationQueueJob | None,
        outputs: tuple[GenerationJobOutputRecord, ...],
    ) -> None:
        """Store fake jobs and output records."""

        self._job = job
        self._outputs = outputs

    def job_for_result_replay(self, job_id: str) -> GenerationQueueJob | None:
        """Return the fake job when ids match."""

        if self._job is not None and self._job.job_id == job_id:
            return self._job
        return None

    def output_records_for_job(
        self,
        job_id: str,
    ) -> tuple[GenerationJobOutputRecord, ...]:
        """Return fake output records for the requested job."""

        return tuple(output for output in self._outputs if output.job_id == job_id)


class _RecipeParser:
    """Return one deterministic parsed Sugar workflow."""

    def parse_recipe_script(self, sugar_script_text: str) -> ParsedSugarScript:
        """Parse fake script text."""

        assert sugar_script_text == "sugar text"
        return ParsedSugarScript(
            buffers=OrderedDict(
                {
                    "Base": OrderedDict(
                        {
                            "cube_id": "cube.load",
                            "version": "1",
                            "nodes": {},
                        }
                    )
                }
            ),
            global_overrides={"seed": {"value": 1234}},
            global_override_selections={"seed": True},
            field_control_states_by_alias={
                "Base": {"ksampler": {"seed": SeedControlState(SeedMode.FIXED)}}
            },
            override_control_states={"seed": SeedControlState(SeedMode.FIXED)},
            model_hashes_by_field={},
            prompt_lora_hashes_by_field={},
            project_name=None,
        )


def _job(job_id: str) -> GenerationQueueJob:
    """Build one fake queue job."""

    return GenerationQueueJob(
        job_id=job_id,
        snapshot=GenerationJobSnapshot(
            workflow_id="workflow-1",
            workflow_name="Portrait Workflow",
            sugar_script_text="sugar text",
        ),
        created_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        status="completed",
    )


def _output(
    job_id: str,
    *,
    sequence: int,
    path: Path,
    scene_count: int | None = None,
    metadata: dict[str, object] | None = None,
) -> GenerationJobOutputRecord:
    """Build one fake persisted output row."""

    return GenerationJobOutputRecord(
        job_id=job_id,
        output_path=path,
        node_id="12",
        created_at=datetime(2026, 5, 8, sequence, tzinfo=timezone.utc),
        sequence=sequence,
        source_key="Base:SaveImage",
        source_label="Save Image",
        scene_run_id="scene-run" if scene_count else None,
        scene_key="scene-a" if scene_count else None,
        scene_title="Scene A" if scene_count else None,
        scene_order=0 if scene_count else None,
        scene_count=scene_count,
        node_title="Save",
        metadata={} if metadata is None else metadata,
    )
