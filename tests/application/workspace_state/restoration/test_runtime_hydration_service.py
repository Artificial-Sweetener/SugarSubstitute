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

"""Tests for versioned workspace runtime hydration."""

from __future__ import annotations

from pathlib import Path

from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.workspace_state.workspace_runtime_hydration_service import (
    WorkspaceRuntimeHydrationService,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)
from tests.support.workspace_runtime_hydration import (
    CubeLoaderStub as _CubeLoader,
)
from tests.support.workspace_runtime_hydration import (
    NodeBehaviorStub as _NodeBehavior,
)
from tests.support.workspace_runtime_hydration import cube_state as _cube
from tests.support.workspace_runtime_hydration import workspace_snapshot as _snapshot


def test_restore_hydrates_by_saved_cube_version() -> None:
    """Hydration should call the version loader with the persisted version."""

    loader = _CubeLoader()
    service = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=_NodeBehavior(),
    )

    result = service.hydrate(
        _snapshot(
            [
                _cube(alias="Old", version="1.0"),
                _cube(alias="New", version="2.0"),
            ]
        )
    )

    assert result.warnings == ()
    assert loader.load_calls == [
        ("owner/repo/demo.cube", "1.0"),
        ("owner/repo/demo.cube", "2.0"),
    ]
    restored = result.snapshot.workflows[0].workflow.cubes
    assert restored["Old"].version == "1.0"
    assert restored["New"].version == "2.0"


def test_restore_reuses_cache_for_identical_cube_version() -> None:
    """Hydration cache should be keyed by cube id and version."""

    loader = _CubeLoader()
    service = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=_NodeBehavior(),
    )

    service.hydrate(
        _snapshot([_cube(alias="A", version="1.0"), _cube(alias="B", version="1.0")])
    )

    assert loader.load_calls == [("owner/repo/demo.cube", "1.0")]


def test_restore_preserves_bypassed_cube_state_after_hydration() -> None:
    """Hydration should keep workflow-owned bypass state from the snapshot."""

    loader = _CubeLoader()
    service = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=_NodeBehavior(),
    )

    result = service.hydrate(
        _snapshot([_cube(alias="Muted", version="1.0", bypassed=True)])
    )

    restored = result.snapshot.workflows[0].workflow.cubes["Muted"]
    assert restored.bypassed is True


def test_restore_skips_cube_without_saved_version() -> None:
    """Missing restored versions should fail with an actionable warning."""

    loader = _CubeLoader()
    service = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=_NodeBehavior(),
    )

    result = service.hydrate(_snapshot([_cube(alias="Missing", version="")]))

    assert loader.load_calls == []
    assert "has no persisted cube version" in result.warnings[0]


def test_restore_preserves_cube_when_runtime_load_fails() -> None:
    """Transient backend load failures must not erase persisted cube state."""

    class _FailingCubeLoader(_CubeLoader):
        """Raise like an unavailable backend during versioned cube load."""

        def load_cube_definition_version(
            self,
            cube_id: str,
            version: str,
            *,
            cube_load_trace_id: str = "",
        ) -> LoadedCubeDefinition:
            """Fail after recording the attempted runtime load."""

            self.load_calls.append((cube_id, version))
            raise RuntimeError("backend unavailable")

    restored_cube = _cube(alias="Restored", version="1.0")
    loader = _FailingCubeLoader()
    service = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=_NodeBehavior(),
    )

    result = service.hydrate(_snapshot([restored_cube]))

    workflow = result.snapshot.workflows[0]
    assert loader.load_calls == [("owner/repo/demo.cube", "1.0")]
    assert workflow.workflow.cubes["Restored"] is not restored_cube
    assert workflow.workflow.cubes["Restored"].cube_id == restored_cube.cube_id
    assert workflow.workflow.stack_order == ["Restored"]
    assert workflow.active_cube_alias == "Restored"
    assert "runtime hydration failed" in result.warnings[0]


def test_restore_preserves_direct_workflow_without_cube_runtime_calls() -> None:
    """Direct documents should bypass cube hydration without losing shared state."""

    direct_workflow = DirectWorkflowState(
        source_path=Path("workflows/direct.json"),
        source_workflow={"nodes": {"1": {"class_type": "KSampler"}}},
        buffer={
            "nodes": {
                "1": {
                    "class_type": "KSampler",
                    "inputs": {"seed": 11},
                }
            }
        },
        ui={"expanded": {"1": False}},
        dirty=True,
    )
    workflow = WorkflowState(
        direct_workflow=direct_workflow,
        global_overrides={"seed": {"value": 13}},
    )
    snapshot = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="direct",
                tab_label="Direct",
                workflow=workflow,
            ),
        ),
        tab_order=("direct",),
        active_route="direct",
        active_workflow_id="direct",
    )
    loader = _CubeLoader()
    service = WorkspaceRuntimeHydrationService(
        cube_load_service=loader,
        node_behavior_service=_NodeBehavior(),
    )

    result = service.hydrate(snapshot)

    restored = result.snapshot.workflows[0]
    assert loader.load_calls == []
    assert restored.workflow.direct_workflow is direct_workflow
    assert restored.workflow.global_overrides == {"seed": {"value": 13}}
    assert restored.active_cube_alias is None
    assert result.warnings == ()
