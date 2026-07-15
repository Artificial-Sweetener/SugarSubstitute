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

"""Cover generation-result workspace append orchestration outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace

from pytest import MonkeyPatch

from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.presentation.shell import (
    generation_result_workspace_materializer as materializer_mod,
)
from substitute.presentation.shell.generation_result_workspace_materializer import (
    GenerationResultWorkspaceMaterializer,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)


def test_generation_result_workspace_append_hydrates_before_materialization(
    monkeypatch: MonkeyPatch,
) -> None:
    """Queue result replay should append only after runtime restore hydration."""

    raw_snapshot = _workspace(active_route="job-raw")
    unique_snapshot = _workspace(active_route="job-open")
    hydrated_snapshot = _workspace(active_route="job-hydrated")
    events: list[str] = []
    shell = SimpleNamespace()

    def make_unique(snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot:
        """Record workflow-id uniquing and return the opened-tab snapshot."""

        assert snapshot is raw_snapshot
        events.append("unique")
        return unique_snapshot

    def hydrate(snapshot: WorkspaceSnapshot, *, operation: str) -> WorkspaceSnapshot:
        """Record queue result hydration and return the hydrated snapshot."""

        assert snapshot is unique_snapshot
        assert operation == "materialize_generation_result_workspace"
        assert snapshot.shell_layout is None
        events.append("hydrate")
        return hydrated_snapshot

    class _Materializer:
        """Record the snapshot passed to append materialization."""

        def materialize_into_existing_workspace(
            self,
            snapshot: WorkspaceSnapshot,
            port: object,
        ) -> object:
            """Record append materialization and return deterministic warnings."""

            assert snapshot is hydrated_snapshot
            assert snapshot.shell_layout is None
            assert isinstance(port, ShellWorkspaceMaterializationPort)
            events.append("materialize")
            return SimpleNamespace(warnings=("restored output skipped",))

    shell.restored_workflow_materializer = SimpleNamespace(
        snapshot_with_unique_open_ids=make_unique
    )
    shell.workspace_restore_controller = SimpleNamespace(
        hydrate_restored_workspace_snapshot=hydrate
    )
    monkeypatch.setattr(
        materializer_mod,
        "WorkspaceMaterializationService",
        _Materializer,
    )

    warnings = GenerationResultWorkspaceMaterializer(
        shell
    ).materialize_generation_result_workspace(raw_snapshot)

    assert events == ["unique", "hydrate", "materialize"]
    assert warnings == ("restored output skipped",)


def _workspace(*, active_route: str) -> WorkspaceSnapshot:
    """Build a minimal workspace snapshot for append tests."""

    workflow = WorkflowSnapshot(
        workflow_id=active_route,
        tab_label="Result",
        workflow=WorkflowState(),
    )
    return WorkspaceSnapshot(
        schema_version="1",
        workflows=(workflow,),
        tab_order=(workflow.workflow_id,),
        active_route=active_route,
        active_workflow_id=workflow.workflow_id,
        shell_layout=None,
    )
