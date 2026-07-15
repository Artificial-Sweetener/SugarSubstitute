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

"""Warm restored cube definitions before visible workspace hydration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.cubes import LoadedCubeDefinition
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger(
    "application.workspace_state.restored_cube_definition_warmup_service"
)


class RestoredCubeDefinitionLoadServiceProtocol(Protocol):
    """Describe cube definition loading required for restore warmup."""

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return one loaded cube definition for cache warmup."""


@dataclass(frozen=True, slots=True)
class RestoredCubeDefinitionWarmupFailure:
    """Describe one restored cube definition that failed to warm."""

    workflow_id: str
    alias: str
    cube_id: str
    error: str


@dataclass(frozen=True, slots=True)
class RestoredCubeDefinitionWarmupResult:
    """Describe restored cube definition warmup coverage."""

    requested_count: int
    warmed_count: int
    skipped_count: int
    failed_count: int
    failures: tuple[RestoredCubeDefinitionWarmupFailure, ...]


@dataclass(frozen=True, slots=True)
class _RestoredCubeReference:
    """Identify one restored cube definition to warm."""

    workflow_id: str
    alias: str
    cube_id: str


class RestoredCubeDefinitionWarmupService:
    """Warm restored cube definitions through the normal cube load service."""

    def warm(
        self,
        snapshot: WorkspaceSnapshot | None,
        cube_load_service: RestoredCubeDefinitionLoadServiceProtocol,
    ) -> RestoredCubeDefinitionWarmupResult:
        """Warm process-cached cube definitions for one restored workspace."""

        references = _restored_cube_references(snapshot)
        failures: list[RestoredCubeDefinitionWarmupFailure] = []
        warmed_count = 0
        trace_mark(
            "restore_cube_definition_warmup.start",
            requested_count=len(references),
            workspace_present=snapshot is not None,
        )
        with trace_span(
            "restore_cube_definition_warmup.run",
            requested_count=len(references),
            workspace_present=snapshot is not None,
        ):
            for reference in references:
                trace_id = f"restore-warmup:{reference.workflow_id}:{reference.alias}"
                try:
                    with trace_span(
                        "restore_cube_definition_warmup.cube",
                        workflow_id=reference.workflow_id,
                        cube_alias=reference.alias,
                        cube_id=reference.cube_id,
                    ):
                        cube_load_service.load_cube_definition(
                            reference.cube_id,
                            cube_load_trace_id=trace_id,
                        )
                except (
                    LookupError,
                    OSError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as error:
                    failure = RestoredCubeDefinitionWarmupFailure(
                        workflow_id=reference.workflow_id,
                        alias=reference.alias,
                        cube_id=reference.cube_id,
                        error=repr(error),
                    )
                    failures.append(failure)
                    trace_mark(
                        "restore_cube_definition_warmup.cube.skip",
                        workflow_id=reference.workflow_id,
                        cube_alias=reference.alias,
                        cube_id=reference.cube_id,
                        error=repr(error),
                    )
                    log_warning(
                        _LOGGER,
                        "Failed to warm restored cube definition",
                        workflow_id=reference.workflow_id,
                        cube_alias=reference.alias,
                        cube_id=reference.cube_id,
                        error=error,
                    )
                    continue
                warmed_count += 1
        result = RestoredCubeDefinitionWarmupResult(
            requested_count=len(references),
            warmed_count=warmed_count,
            skipped_count=0,
            failed_count=len(failures),
            failures=tuple(failures),
        )
        trace_mark(
            "restore_cube_definition_warmup.end",
            requested_count=result.requested_count,
            warmed_count=result.warmed_count,
            skipped_count=result.skipped_count,
            failed_count=result.failed_count,
        )
        return result


def _restored_cube_references(
    snapshot: WorkspaceSnapshot | None,
) -> tuple[_RestoredCubeReference, ...]:
    """Return active-first unique restored cube references."""

    if snapshot is None:
        return ()
    workflows_by_id = {
        workflow.workflow_id: workflow for workflow in snapshot.workflows
    }
    active_workflow_id = _active_workflow_id(snapshot)
    ordered_workflow_ids = _workflow_warmup_order(snapshot, active_workflow_id)
    seen_cube_ids: set[str] = set()
    references: list[_RestoredCubeReference] = []
    for workflow_id in ordered_workflow_ids:
        workflow = workflows_by_id.get(workflow_id)
        if workflow is None:
            continue
        references.extend(
            _workflow_cube_references(
                workflow,
                seen_cube_ids=seen_cube_ids,
            )
        )
    return tuple(references)


def _workflow_cube_references(
    workflow: WorkflowSnapshot,
    *,
    seen_cube_ids: set[str],
) -> list[_RestoredCubeReference]:
    """Return unique restored cube references for one workflow."""

    references: list[_RestoredCubeReference] = []
    for alias in workflow.workflow.stack_order:
        cube = workflow.workflow.cubes.get(alias)
        if cube is None:
            continue
        cube_id = cube.cube_id.strip()
        if not cube_id or cube_id in seen_cube_ids:
            continue
        seen_cube_ids.add(cube_id)
        references.append(
            _RestoredCubeReference(
                workflow_id=workflow.workflow_id,
                alias=alias,
                cube_id=cube_id,
            )
        )
    return references


def _active_workflow_id(snapshot: WorkspaceSnapshot) -> str:
    """Return normalized active workflow id for warmup prioritization."""

    if snapshot.active_workflow_id in snapshot.tab_order:
        return snapshot.active_workflow_id
    return snapshot.active_route if snapshot.active_route in snapshot.tab_order else ""


def _workflow_warmup_order(
    snapshot: WorkspaceSnapshot,
    active_workflow_id: str,
) -> tuple[str, ...]:
    """Return tab order with the active workflow first when present."""

    ordered = list(snapshot.tab_order)
    if active_workflow_id in ordered:
        ordered.remove(active_workflow_id)
        ordered.insert(0, active_workflow_id)
    return tuple(ordered)


__all__ = [
    "RestoredCubeDefinitionLoadServiceProtocol",
    "RestoredCubeDefinitionWarmupFailure",
    "RestoredCubeDefinitionWarmupResult",
    "RestoredCubeDefinitionWarmupService",
]
