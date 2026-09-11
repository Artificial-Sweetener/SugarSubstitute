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

"""Restore native Comfy graphs through SugarCubes-owned analysis."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from substitute.domain.comfy_workflow import (
    CanonicalCubeGraphAnalysis,
    DirectWorkflowState,
)
from substitute.domain.common import JsonObject
from substitute.domain.cubes import project_editable_cube_document
from substitute.domain.workspace_snapshot import WorkflowSnapshot
from substitute.domain.workspace_snapshot.cube_projection_codec import (
    capture_cube_projection_state,
    restore_cube_projection_state,
    transfer_cube_projection_state,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workspace_state.native_graph_restore_service")


class CubeWorkflowAnalyzerProtocol(Protocol):
    """Expose SugarCubes whole-graph normalization and Cube analysis."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return one complete normalized graph and derived Cube projection."""

    def create_cube_workflow(
        self,
        cubes: Sequence[Mapping[str, object]],
    ) -> CanonicalCubeGraphAnalysis:
        """Create one native graph from an ordered legacy Cube stack."""


@dataclass(frozen=True, slots=True)
class NativeGraphRestoreResult:
    """Return a restored native graph and any fail-closed diagnostic."""

    snapshot: WorkflowSnapshot
    warning: str | None = None


class NativeGraphRestoreService:
    """Rebuild Cube projections from the one persisted native graph."""

    def __init__(self, analyzer: CubeWorkflowAnalyzerProtocol) -> None:
        """Bind the sole Cube graph analysis owner."""

        self._analyzer = analyzer

    def restore(self, snapshot: WorkflowSnapshot) -> NativeGraphRestoreResult:
        """Analyze one graph once and derive its Cube editor projection."""

        workflow = snapshot.workflow
        direct = workflow.direct_workflow
        if direct is None:
            raise ValueError("Native graph restore requires a Comfy workflow document.")
        try:
            reconciled_document = DirectWorkflowState(
                source_path=direct.source_path,
                source_workflow=deepcopy(direct.source_workflow),
                buffer=deepcopy(direct.buffer),
                ui=deepcopy(direct.ui),
                dirty=direct.dirty,
                cube_projection_state=deepcopy(direct.cube_projection_state),
            )
            unresolved_fields = reconciled_document.reconcile_canonical_projection()
            if unresolved_fields:
                log_warning(
                    _LOGGER,
                    "Preserved editor values without canonical widget origins",
                    workflow_id=snapshot.workflow_id,
                    unresolved_field_count=len(unresolved_fields),
                    unresolved_fields=unresolved_fields,
                )
            source_workflow = reconciled_document.source_workflow
            analysis = self._analyzer.analyze(source_workflow)
            canonical_document = DirectWorkflowState(
                source_path=direct.source_path,
                source_workflow=analysis.workflow,
                buffer=reconciled_document.buffer,
                ui=reconciled_document.ui,
                dirty=direct.dirty,
                cube_analysis=analysis,
                cube_projection_state=direct.cube_projection_state,
            )
            restored_workflow = deepcopy(workflow)
            restored_workflow.cubes = {}
            restored_workflow.stack_order = []
            restored_workflow.install_canonical_graph(canonical_document)
            restore_cube_projection_state(
                restored_workflow.cubes,
                direct.cube_projection_state,
            )
        except (LookupError, OSError, RuntimeError, TypeError, ValueError) as error:
            warning = (
                f"Preserved restored native workflow {snapshot.workflow_id} without "
                "a Cube stack because SugarCubes analysis failed."
            )
            log_warning(
                _LOGGER,
                "restore native workflow analysis failed closed",
                workflow_id=snapshot.workflow_id,
                error=error,
            )
            return NativeGraphRestoreResult(
                replace(snapshot, active_cube_alias=None),
                warning,
            )
        active_cube_alias = (
            snapshot.active_cube_alias
            if snapshot.active_cube_alias in restored_workflow.cubes
            else (
                restored_workflow.stack_order[0]
                if restored_workflow.stack_order
                else None
            )
        )
        return NativeGraphRestoreResult(
            replace(
                snapshot,
                workflow=restored_workflow,
                active_cube_alias=active_cube_alias,
            )
        )

    def migrate_legacy(self, snapshot: WorkflowSnapshot) -> NativeGraphRestoreResult:
        """Replace one hydrated legacy stack with SugarCubes' native graph."""

        workflow = snapshot.workflow
        if workflow.direct_workflow is not None:
            raise ValueError("Legacy migration requires a workflow without a graph.")
        ordered_cubes = [
            workflow.cubes[alias]
            for alias in workflow.stack_order
            if alias in workflow.cubes
        ]
        if not ordered_cubes:
            return NativeGraphRestoreResult(snapshot)
        try:
            analysis = self._analyzer.create_cube_workflow(
                [
                    {
                        "instance_id": f"legacy-{index}",
                        "alias": cube.alias,
                        "bypassed": cube.bypassed,
                        "document": project_editable_cube_document(
                            cube_id=cube.cube_id,
                            version=cube.version,
                            buffer=cube.buffer,
                            canonical_metadata=_canonical_cube_metadata(cube),
                        ),
                    }
                    for index, cube in enumerate(ordered_cubes, start=1)
                ]
            )
            restored_workflow = deepcopy(workflow)
            document = DirectWorkflowState(
                source_path=snapshot.document_source_path or Path(),
                source_workflow=analysis.workflow,
                buffer={"nodes": {}},
                dirty=True,
                cube_analysis=analysis,
            )
            restored_workflow.install_canonical_graph(
                document,
                projection_sources=workflow.cubes,
            )
            transfer_cube_projection_state(
                workflow.cubes,
                restored_workflow.cubes,
            )
            document.cube_projection_state = capture_cube_projection_state(
                restored_workflow.cubes
            )
        except (LookupError, OSError, RuntimeError, TypeError, ValueError) as error:
            warning = (
                f"Preserved legacy workflow {snapshot.workflow_id} because its "
                "one-time native graph migration failed."
            )
            log_warning(
                _LOGGER,
                "legacy Cube workflow migration failed closed",
                workflow_id=snapshot.workflow_id,
                error=error,
            )
            return NativeGraphRestoreResult(snapshot, warning)
        active_cube_alias = (
            snapshot.active_cube_alias
            if snapshot.active_cube_alias in restored_workflow.cubes
            else restored_workflow.stack_order[0]
        )
        return NativeGraphRestoreResult(
            replace(
                snapshot,
                workflow=restored_workflow,
                active_cube_alias=active_cube_alias,
                document_dirty=True,
            )
        )


def _canonical_cube_metadata(cube: object) -> Mapping[str, object] | None:
    """Prefer complete canonical metadata retained beside runtime graph state."""

    ui_payload = getattr(cube, "ui", None)
    canonical = (
        ui_payload.get("canonical_cube") if isinstance(ui_payload, Mapping) else None
    )
    if isinstance(canonical, Mapping):
        return canonical
    fallback = getattr(cube, "original_cube", None)
    return fallback if isinstance(fallback, Mapping) else None


__all__ = [
    "CubeWorkflowAnalyzerProtocol",
    "NativeGraphRestoreResult",
    "NativeGraphRestoreService",
]
