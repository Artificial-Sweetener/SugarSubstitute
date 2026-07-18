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

"""Build restorable workspace snapshots from live generation queue state."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from substitute.domain.common import JsonObject
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.generation import (
    GENERATION_RESULT_SNAPSHOT_SCHEMA_VERSION,
    GenerationJobOutputRecord,
    GenerationQueueJob,
    GenerationResultSnapshot,
)
from substitute.domain.recipes.sugar_ast import ParsedSugarScript
from substitute.domain.workflow import CubeState, OutputFocusMode, WorkflowState
from substitute.domain.workspace_snapshot import (
    ImageMetaSnapshot,
    OutputImageReference,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.generation.generation_result_snapshot_service")


class RecipeScriptParser(Protocol):
    """Describe recipe parsing needed for generation result replay."""

    def parse_recipe_script(self, sugar_script_text: str) -> ParsedSugarScript:
        """Parse Sugar text into workflow buffers and global overrides."""


class LiveGenerationResultLookup(Protocol):
    """Provide current-session generation jobs and outputs for replay."""

    def job_for_result_replay(self, job_id: str) -> GenerationQueueJob | None:
        """Return one visible live queue job by id."""

    def output_records_for_job(
        self,
        job_id: str,
    ) -> tuple[GenerationJobOutputRecord, ...]:
        """Return current-session output records for one visible queue job."""


@dataclass(frozen=True, slots=True)
class GenerationResultSnapshotBuildResult:
    """Carry one generated result snapshot and non-fatal replay warnings."""

    snapshot: GenerationResultSnapshot | None
    warnings: tuple[str, ...]


class GenerationResultSnapshotService:
    """Build immutable job-result workspace snapshots for live queue replay."""

    def __init__(
        self,
        *,
        live_results: LiveGenerationResultLookup,
        recipe_parser: RecipeScriptParser,
    ) -> None:
        """Store live queue and recipe parsing dependencies."""

        self._live_results = live_results
        self._recipe_parser = recipe_parser

    def build_for_live_job(self, job_id: str) -> GenerationResultSnapshotBuildResult:
        """Build a restorable snapshot for one visible current-session job."""

        job = self._live_results.job_for_result_replay(job_id)
        if job is None:
            log_warning(
                _LOGGER,
                "Generation result snapshot skipped; live job missing",
                job_id=job_id,
            )
            return GenerationResultSnapshotBuildResult(
                snapshot=None,
                warnings=(f"Generation job {job_id} was not found.",),
            )
        outputs = self._live_results.output_records_for_job(job_id)
        workflow_id = self._workflow_id_for_job(job_id)
        if job.snapshot.direct_workflow_plan is not None:
            workflow = self._workflow_from_direct_graph(
                job_id=job_id,
                graph=job.snapshot.direct_workflow_plan.authored_api_graph,
            )
        else:
            parsed_script = self._recipe_parser.parse_recipe_script(
                job.snapshot.sugar_script_text
            )
            workflow = self._workflow_from_script(parsed_script)
        output_references = tuple(
            self._output_reference(
                job_id=job_id,
                workflow_name=job.snapshot.workflow_name,
                output=output,
            )
            for output in outputs
        )
        output_ids = [UUID(reference.image_id) for reference in output_references]
        workflow.output_image_uuids = output_ids
        if output_ids:
            workflow.output_focus_mode = OutputFocusMode.MANUAL
            workflow.active_output_uuid = output_ids[-1]
            self._restore_output_group_focus(workflow, outputs[-1])
        workspace = WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(
                WorkflowSnapshot(
                    workflow_id=workflow_id,
                    tab_label=job.snapshot.workflow_name,
                    workflow=workflow,
                    active_cube_alias=workflow.stack_order[-1]
                    if workflow.stack_order
                    else None,
                    input_images=(),
                    input_masks=(),
                    output_images=output_references,
                ),
            ),
            tab_order=(workflow_id,),
            active_route=workflow_id,
            shell_layout=None,
        )
        result = GenerationResultSnapshot(
            schema_version=GENERATION_RESULT_SNAPSHOT_SCHEMA_VERSION,
            job_id=job_id,
            job=job,
            workspace=workspace,
        )
        log_info(
            _LOGGER,
            "Built live generation result snapshot",
            job_id=job_id,
            output_count=len(output_references),
            workflow_id=workflow_id,
        )
        return GenerationResultSnapshotBuildResult(snapshot=result, warnings=())

    def _workflow_from_script(self, parsed_script: ParsedSugarScript) -> WorkflowState:
        """Build workflow state from parsed Sugar buffers."""

        workflow = WorkflowState()
        workflow.global_overrides = parsed_script.global_overrides
        workflow.global_override_selections = parsed_script.global_override_selections
        workflow.override_control_states = dict(parsed_script.override_control_states)
        for alias, buffer in parsed_script.buffers.items():
            workflow.stack_order.append(alias)
            workflow.cubes[alias] = CubeState(
                cube_id=str(buffer.get("cube_id", "")),
                version=str(buffer.get("version", "")),
                alias=alias,
                original_cube={},
                buffer=cast(JsonObject, dict(buffer)),
                field_control_states={
                    str(node): dict(field_states)
                    for node, field_states in parsed_script.field_control_states_by_alias.get(
                        alias,
                        {},
                    ).items()
                },
            )
        return workflow

    @staticmethod
    def _workflow_from_direct_graph(
        *,
        job_id: str,
        graph: JsonObject,
    ) -> WorkflowState:
        """Build a restorable editor document from a queued direct API graph."""

        return WorkflowState(
            direct_workflow=DirectWorkflowState(
                source_path=Path(f"generation-{job_id}.json"),
                source_workflow={"nodes": [], "links": []},
                buffer={"nodes": deepcopy(graph)},
            )
        )

    @staticmethod
    def _restore_output_group_focus(
        workflow: WorkflowState,
        output: GenerationJobOutputRecord,
    ) -> None:
        """Restore output grouping focus from persisted output metadata."""

        workflow.active_output_set_index = 1
        workflow.active_output_source_key = output.source_key or output.node_id
        workflow.active_output_scene_key = output.scene_key
        workflow.active_output_scene_overview = bool(
            output.scene_run_id and output.scene_count and output.scene_count > 1
        )
        if workflow.active_output_scene_overview:
            workflow.active_output_source_key = None
            workflow.active_output_scene_key = None

    def _output_reference(
        self,
        *,
        job_id: str,
        workflow_name: str,
        output: GenerationJobOutputRecord,
    ) -> OutputImageReference:
        """Build one output reference with deterministic replay identity."""

        image_id = self._output_image_id(job_id=job_id, output=output)
        source_key = output.source_key or output.node_id
        source_label = output.source_label or output.node_title or output.node_id
        return OutputImageReference(
            image_id=str(image_id),
            path=output.output_path,
            metadata=ImageMetaSnapshot(
                workflow_name=workflow_name,
                cube_name=source_label,
                image_number=output.sequence,
                suffix=output.output_path.suffix,
                path=output.output_path,
                source_key=source_key,
                source_label=source_label,
                node_id=output.node_id,
                generation_run_id=job_id,
                list_index=_optional_non_negative_int(
                    output.metadata.get("list_index")
                ),
                batch_index=_optional_non_negative_int(
                    output.metadata.get("batch_index")
                ),
                scene_run_id=output.scene_run_id,
                scene_key=output.scene_key,
                scene_title=output.scene_title,
                scene_order=output.scene_order,
                scene_count=output.scene_count,
                width=_optional_int(output.metadata.get("width")),
                height=_optional_int(output.metadata.get("height")),
                cube_execution_duration_ms=_optional_float(
                    output.metadata.get("cube_execution_duration_ms")
                ),
            ),
            sequence=output.sequence,
        )

    @staticmethod
    def _workflow_id_for_job(job_id: str) -> str:
        """Return a stable workflow id for one replayed generation job."""

        return f"job-{job_id}"

    @staticmethod
    def _output_image_id(
        *,
        job_id: str,
        output: GenerationJobOutputRecord,
    ) -> UUID:
        """Return a deterministic UUID for one persisted job output."""

        return uuid5(
            NAMESPACE_URL,
            f"substitute:generation-output:{job_id}:{output.sequence}:{output.output_path}",
        )


def _optional_int(value: object) -> int | None:
    """Return a positive integer metadata value when present."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        integer = int(value)
        return integer if integer > 0 else None
    return None


def _optional_non_negative_int(value: object) -> int | None:
    """Return a non-negative integer metadata value when present."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer():
        integer = int(value)
        return integer if integer >= 0 else None
    return None


def _optional_float(value: object) -> float | None:
    """Return a non-negative float metadata value when present."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        number = float(value)
        return number if number >= 0.0 else None
    return None


__all__ = [
    "GenerationResultSnapshotBuildResult",
    "GenerationResultSnapshotService",
    "LiveGenerationResultLookup",
    "RecipeScriptParser",
]
