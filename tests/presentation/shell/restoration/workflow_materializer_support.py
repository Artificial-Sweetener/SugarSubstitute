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

"""Provide restored-workflow materializer doubles."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    WorkflowSnapshot,
)
from substitute.presentation.shell.workflow_surface_results import WorkflowUiSurfaces


class _TabItem:
    """Expose a tab label for uniqueness checks."""

    def __init__(self, label: str) -> None:
        """Store the tab label."""

        self._label = label

    def text(self) -> str:
        """Return the stored tab label."""

        return self._label


class _WorkflowTabbar:
    """Record restored tab creation."""

    def __init__(self) -> None:
        """Initialize tab records."""

        self.items: list[_TabItem] = []
        self.tabs: list[tuple[str, str]] = []

    def addTab(self, workflow_id: str, label: str) -> None:
        """Record a restored workflow tab."""

        self.tabs.append((workflow_id, label))
        self.items.append(_TabItem(label))


class _WorkflowSessionService:
    """Record restored workflow session registration."""

    def __init__(self, *, active_workflow_id: str = "") -> None:
        """Initialize workflow session state."""

        self.active_workflow_id = active_workflow_id
        self.workflows: dict[str, WorkflowState] = {}

    def add_existing_workflow(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        *,
        activate: bool,
    ) -> object:
        """Record an existing workflow and return a transition record."""

        previous_active_workflow_id = self.active_workflow_id
        self.workflows[workflow_id] = workflow
        if activate:
            self.active_workflow_id = workflow_id
        return SimpleNamespace(
            workflow_id=workflow_id,
            workflow=workflow,
            previous_active_workflow_id=previous_active_workflow_id,
            active_changed=activate
            and previous_active_workflow_id
            and previous_active_workflow_id != workflow_id,
        )


class _RestoredCubeStack:
    """Record restored cube-stack tab operations."""

    def __init__(self) -> None:
        """Initialize cube-stack records."""

        self.tabs: list[dict[str, object]] = []
        self.icons: dict[int, object] = {}
        self.current_index = -1

    def clear(self) -> None:
        """Clear all stack tabs."""

        self.tabs.clear()
        self.icons.clear()
        self.current_index = -1

    def count(self) -> int:
        """Return tab count."""

        return len(self.tabs)

    def insertTab(self, index: int, *, routeKey: str, text: str) -> None:
        """Record tab insertion."""

        self.tabs.insert(index, {"routeKey": routeKey, "text": text})

    def setTabIcon(self, index: int, icon: object) -> None:
        """Record tab icon assignment."""

        self.icons[index] = icon

    def tabItem(self, index: int) -> object:
        """Return one fake tab item."""

        return SimpleNamespace(routeKey=lambda: self.tabs[index]["routeKey"])

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Accept rich tab presentation from the presenter."""

    def setCurrentIndex(self, index: int) -> None:
        """Record current tab index."""

        self.current_index = index

    def currentIndex(self) -> int:
        """Return current tab index."""

        return self.current_index


class _WorkflowUiShell:
    """Provide the shell API needed by deferred UI hydration."""

    def __init__(self, snapshot: WorkflowSnapshot) -> None:
        """Initialize shell state with one deferred snapshot."""

        self.cube_stacks: dict[str, _RestoredCubeStack] = {}
        self.editor_panels: dict[str, object] = {}
        self.cube_stack_container = SimpleNamespace(
            setCurrentWidget=lambda _widget: None
        )
        self.editor_panel_container = SimpleNamespace(
            setCurrentWidget=lambda _widget: None
        )
        self.cube_icon_factory = SimpleNamespace(icon_for_cube=lambda **_kwargs: "icon")
        self._pending_restored_workflow_snapshots = {snapshot.workflow_id: snapshot}
        self.created: list[tuple[str, bool]] = []
        self.cube_stack: object | None = None
        self.editor_panel: object | None = None
        self.workflow_ui_factory = SimpleNamespace(
            create_workflow_ui=self._create_new_workflow_ui
        )

    def _create_new_workflow_ui(
        self,
        workflow_id: str,
        *,
        set_as_current: bool = True,
    ) -> WorkflowUiSurfaces:
        """Create fake workflow-scoped widgets."""

        self.created.append((workflow_id, set_as_current))
        stack = self.cube_stacks.setdefault(workflow_id, _RestoredCubeStack())
        editor_panel = self.editor_panels.setdefault(workflow_id, object())
        return WorkflowUiSurfaces(
            cube_stack=stack,
            editor_panel=editor_panel,
            created=True,
        )


def _workflow_snapshot(
    workflow_id: str = "wf-a",
    tab_label: str = "Workflow",
) -> WorkflowSnapshot:
    """Build a workflow snapshot with one cube."""

    cube_state = CubeState(
        cube_id="pack/CubeA",
        version="1.0",
        alias="CubeA",
        original_cube={},
        buffer={},
        display_name="Cube A",
        ui={},
    )
    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label=tab_label,
        workflow=WorkflowState(cubes={"CubeA": cube_state}, stack_order=["CubeA"]),
        active_cube_alias="CubeA",
    )
