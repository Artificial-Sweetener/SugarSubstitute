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

"""Tests for restored cube definition startup warmup."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.workspace_state import RestoredCubeDefinitionWarmupService
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


@dataclass
class _CubeLoadService:
    """Record definition warmup calls."""

    failures: set[str] = field(default_factory=set)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return a loaded definition unless configured to fail."""

        self.calls.append((cube_id, cube_load_trace_id))
        if cube_id in self.failures:
            raise LookupError(cube_id)
        return LoadedCubeDefinition(
            cube_id=cube_id,
            version="1.0",
            display_name=cube_id,
            graph={},
            ui_payload={},
            icon=None,
        )


def test_warmup_loads_unique_cube_definitions_active_workflow_first() -> None:
    """Warmup should dedupe cube ids while prioritizing the active workflow."""

    loader = _CubeLoadService()
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            _workflow("wf-a", ("shared", "inactive-only")),
            _workflow("wf-b", ("active-only", "shared")),
        ),
        tab_order=("wf-a", "wf-b"),
        active_route="wf-b",
        active_workflow_id="wf-b",
        shell_layout=None,
    )

    result = RestoredCubeDefinitionWarmupService().warm(snapshot, loader)

    assert result.requested_count == 3
    assert result.warmed_count == 3
    assert result.failed_count == 0
    assert [call[0] for call in loader.calls] == [
        "active-only",
        "shared",
        "inactive-only",
    ]
    assert loader.calls[0][1] == "restore-warmup:wf-b:active-only"


def test_warmup_continues_after_cube_load_failure() -> None:
    """One failed cube warmup should not stop remaining cache priming."""

    loader = _CubeLoadService(failures={"broken"})
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(_workflow("wf-a", ("broken", "ok")),),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=None,
    )

    result = RestoredCubeDefinitionWarmupService().warm(snapshot, loader)

    assert result.requested_count == 2
    assert result.warmed_count == 1
    assert result.failed_count == 1
    assert result.failures[0].cube_id == "broken"
    assert [call[0] for call in loader.calls] == ["broken", "ok"]


def test_warmup_ignores_missing_empty_and_duplicate_cube_ids() -> None:
    """Warmup should only request actionable unique cube ids."""

    loader = _CubeLoadService()
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="A",
                workflow=WorkflowState(
                    cubes={
                        "missing-id": _cube("missing-id", ""),
                        "ok": _cube("ok", "cube.ok"),
                        "dupe": _cube("dupe", "cube.ok"),
                    },
                    stack_order=["unknown", "missing-id", "ok", "dupe"],
                ),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=None,
    )

    result = RestoredCubeDefinitionWarmupService().warm(snapshot, loader)

    assert result.requested_count == 1
    assert result.warmed_count == 1
    assert loader.calls == [("cube.ok", "restore-warmup:wf-a:ok")]


def test_warmup_returns_empty_result_without_workspace() -> None:
    """Missing restore snapshots should be a no-op."""

    loader = _CubeLoadService()

    result = RestoredCubeDefinitionWarmupService().warm(None, loader)

    assert result.requested_count == 0
    assert loader.calls == []


def _workflow(workflow_id: str, cube_ids: tuple[str, ...]) -> WorkflowSnapshot:
    """Build one workflow snapshot with cube ids matching aliases."""

    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label=workflow_id,
        workflow=WorkflowState(
            cubes={cube_id: _cube(cube_id, cube_id) for cube_id in cube_ids},
            stack_order=list(cube_ids),
        ),
    )


def _cube(alias: str, cube_id: str) -> CubeState:
    """Build one restored cube state."""

    return CubeState(
        cube_id=cube_id,
        version="1.0",
        alias=alias,
        original_cube={},
        buffer={},
        display_name=alias,
        ui={},
    )
