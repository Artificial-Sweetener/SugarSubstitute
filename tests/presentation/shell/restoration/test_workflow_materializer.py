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

"""Cover restored workflow UI materialization outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.shell.restored_workflow_materializer import (
    RestoredWorkflowMaterializer,
)
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces


from tests.presentation.shell.restoration.workflow_materializer_support import (
    _RestoredCubeStack,
    _TabItem,
    _WorkflowSessionService,
    _WorkflowTabbar,
    _WorkflowUiShell,
    _workflow_snapshot,
)


def test_snapshot_with_unique_open_ids_remaps_colliding_workflows() -> None:
    """Append restore should avoid open workflow id and tab-label collisions."""

    session = _WorkflowSessionService()
    session.workflows["wf-a"] = WorkflowState()
    tabbar = _WorkflowTabbar()
    tabbar.items = [_TabItem("Untitled Workflow"), _TabItem("Untitled Workflow (2)")]
    shell = SimpleNamespace(
        workflow_session_service=session,
        workflow_tabbar=tabbar,
    )
    snapshot = WorkspaceSnapshot(
        schema_version="1",
        workflows=(_workflow_snapshot(tab_label="Untitled Recipe"),),
        tab_order=("wf-a",),
        active_route="wf-a",
        shell_layout=ShellLayoutSnapshot(),
    )

    result = RestoredWorkflowMaterializer(shell).snapshot_with_unique_open_ids(snapshot)

    assert result.workflows[0].workflow_id == "wf-a-2"
    assert result.workflows[0].tab_label == "Untitled Workflow (3)"
    assert result.tab_order == ("wf-a-2",)
    assert result.active_route == "wf-a-2"
    assert result.shell_layout is None


def test_add_prehydrated_workflow_registers_placeholder_workflow_state() -> None:
    """Prehydration should leave raw restored workflow state pending."""

    session = _WorkflowSessionService()
    tabbar = _WorkflowTabbar()
    shell = SimpleNamespace(
        workflow_session_service=session,
        workflow_tabbar=tabbar,
        _pending_restored_workflow_snapshots={},
    )
    snapshot = _workflow_snapshot(workflow_id="wf-raw", tab_label="Raw")

    RestoredWorkflowMaterializer(shell).add_prehydrated_workflow(
        snapshot,
        activate=True,
    )

    assert session.active_workflow_id == "wf-raw"
    assert session.workflows["wf-raw"].cubes == {}
    assert session.workflows["wf-raw"].stack_order == []
    assert tabbar.tabs == [("wf-raw", "Raw")]
    assert shell._pending_restored_workflow_snapshots == {"wf-raw": snapshot}


def test_add_restored_workflow_defers_inactive_ui_creation() -> None:
    """Inactive restored workflows should register session and tab state only."""

    session = _WorkflowSessionService(active_workflow_id="wf-active")
    tabbar = _WorkflowTabbar()
    shell = SimpleNamespace(
        workflow_session_service=session,
        workflow_tabbar=tabbar,
        _pending_restored_workflow_snapshots={},
        cube_stacks={},
        editor_panels={},
        override_managers={},
    )
    snapshot = _workflow_snapshot(workflow_id="wf-inactive", tab_label="Inactive")

    RestoredWorkflowMaterializer(shell).add_restored_workflow(
        snapshot,
        activate=False,
    )

    assert session.active_workflow_id == "wf-active"
    assert session.workflows["wf-inactive"] is snapshot.workflow
    assert tabbar.tabs == [("wf-inactive", "Inactive")]
    assert shell._pending_restored_workflow_snapshots == {"wf-inactive": snapshot}
    assert shell.cube_stacks == {}
    assert shell.editor_panels == {}


def test_add_restored_workflow_clears_outgoing_override_toolbar_on_activation() -> None:
    """Active restored workflows should clear stale outgoing override controls."""

    session = _WorkflowSessionService(active_workflow_id="wf-old")
    tabbar = _WorkflowTabbar()
    calls: list[str] = []
    shell = SimpleNamespace(
        workflow_session_service=session,
        workflow_tabbar=tabbar,
        _pending_restored_workflow_snapshots={},
        cube_stacks={},
        editor_panels={},
        override_managers={
            "wf-old": SimpleNamespace(
                _clear_all_override_widgets=lambda: calls.append("clear:overrides")
            )
        },
        _clear_all_model_field_load_progress=lambda: calls.append("clear:model"),
        cube_icon_factory=SimpleNamespace(icon_for_cube=lambda **_kwargs: "icon"),
    )

    def create_workflow_ui(
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Record workflow UI creation and return fake widgets."""

        calls.append(f"create:{workflow_id}:{set_as_current}")
        stack = shell.cube_stacks.setdefault(workflow_id, _RestoredCubeStack())
        editor = shell.editor_panels.setdefault(workflow_id, object())
        return WorkflowUiSurfaces(
            cube_stack=stack,
            editor_panel=editor,
            created=True,
        )

    shell.workflow_ui_factory = SimpleNamespace(create_workflow_ui=create_workflow_ui)
    snapshot = _workflow_snapshot(workflow_id="wf-restored", tab_label="Restored")

    RestoredWorkflowMaterializer(shell).add_restored_workflow(
        snapshot,
        activate=True,
    )

    assert "clear:overrides" in calls
    assert calls.index("clear:overrides") < calls.index("create:wf-restored:True")
    assert "clear:model" in calls
    assert shell._pending_restored_workflow_snapshots == {}


def test_ensure_workflow_ui_hydrates_deferred_restored_snapshot() -> None:
    """First activation should create and materialize deferred workflow widgets."""

    snapshot = _workflow_snapshot(workflow_id="wf-inactive", tab_label="Inactive")
    shell = _WorkflowUiShell(snapshot)

    surfaces = RestoredWorkflowMaterializer(shell).ensure_workflow_ui(
        "wf-inactive",
        set_as_current=True,
    )
    cube_stack = surfaces.cube_stack
    editor_panel = surfaces.editor_panel

    assert shell.created == [("wf-inactive", True)]
    assert cube_stack is shell.cube_stacks["wf-inactive"]
    assert editor_panel is shell.editor_panels["wf-inactive"]
    assert cube_stack.tabs == [{"routeKey": "CubeA", "text": "CubeA"}]
    assert cube_stack.current_index == 0
    assert shell._pending_restored_workflow_snapshots == {}


def test_materialize_restored_cube_stack_applies_icons_and_active_cube() -> None:
    """Restored cube stacks should use normal icon metadata from cube state."""

    stack = _RestoredCubeStack()
    icon_calls: list[dict[str, object]] = []

    def icon_for_cube(**kwargs: object) -> str:
        """Record icon resolution arguments and return a resolved icon."""

        icon_calls.append(kwargs)
        return "resolved-icon"

    shell = SimpleNamespace(
        cube_stacks={"wf-a": stack},
        cube_icon_factory=SimpleNamespace(icon_for_cube=icon_for_cube),
    )
    cube_state = CubeState(
        cube_id="pack/CubeA",
        version="1.0",
        alias="CubeA",
        original_cube={},
        buffer={},
        display_name="Cube A",
        ui={
            "cube_icon": "icon-descriptor",
            "catalog_revision": "rev-1",
            "content_hash": "hash-1",
        },
    )
    snapshot = WorkflowSnapshot(
        workflow_id="wf-a",
        tab_label="Restored",
        workflow=WorkflowState(cubes={"CubeA": cube_state}, stack_order=["CubeA"]),
        active_cube_alias="CubeA",
    )

    RestoredWorkflowMaterializer(shell).materialize_restored_cube_stack(snapshot)

    assert stack.tabs == [{"routeKey": "CubeA", "text": "CubeA"}]
    assert stack.icons == {0: "resolved-icon"}
    assert stack.current_index == 0
    assert icon_calls == [
        {
            "cube_id": "pack/CubeA",
            "display_name": "Cube A",
            "icon": "icon-descriptor",
            "catalog_revision": "rev-1",
            "cube_content_hash": "hash-1",
        }
    ]


def test_materialize_restored_cube_stack_applies_fallback_icon_immediately() -> None:
    """Restored cube stacks should not expose iconless tabs after materialization."""

    stack = _RestoredCubeStack()

    def raise_icon_error(**_kwargs: object) -> object:
        """Raise an expected icon resolution failure."""

        raise RuntimeError("icon unavailable")

    shell = SimpleNamespace(
        cube_stacks={"wf-a": stack},
        cube_icon_factory=SimpleNamespace(icon_for_cube=raise_icon_error),
    )
    cube_state = CubeState(
        cube_id="pack/CubeA",
        version="1.0",
        alias="CubeA",
        original_cube={},
        buffer={},
        display_name="Cube A",
        ui={
            "cube_icon": "icon-descriptor",
            "catalog_revision": "rev-1",
            "content_hash": "hash-1",
        },
    )
    snapshot = WorkflowSnapshot(
        workflow_id="wf-a",
        tab_label="Restored",
        workflow=WorkflowState(cubes={"CubeA": cube_state}, stack_order=["CubeA"]),
        active_cube_alias="CubeA",
    )

    RestoredWorkflowMaterializer(shell).materialize_restored_cube_stack(snapshot)

    assert stack.tabs == [{"routeKey": "CubeA", "text": "CubeA"}]
    assert getattr(stack.icons[0], "value", stack.icons[0]) == (
        AppIcon.CUBE_20_FILLED.value
    )
    assert stack.current_index == 0
