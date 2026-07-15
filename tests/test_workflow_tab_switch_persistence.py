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

"""Regression tests for cube-load workflow targeting across tab switches."""

from __future__ import annotations

import types

from substitute.application.execution import CancellationToken, TaskRequest
from tests.execution_testing import ManualTaskHandle


def test_cube_loading_targets_original_workflow_despite_tab_switch(monkeypatch):
    """Queued cube loads should complete against the workflow active at request time."""

    from substitute.application.node_behavior import NodeBehaviorRuntimeState
    from substitute.domain.workflow import CubeState, WorkflowState
    from substitute.presentation.shell import cube_loader

    class FakeQTimer:
        """Queue delayed callbacks so the test controls UI handoff timing."""

        queue = []

        @staticmethod
        def singleShot(_ms, func):
            """Queue one timer callback."""

            FakeQTimer.queue.append(func)

        @staticmethod
        def run_all():
            """Run all queued timer callbacks."""

            while FakeQTimer.queue:
                FakeQTimer.queue.pop(0)()

    monkeypatch.setattr(cube_loader, "QTimer", FakeQTimer)

    class FakeExecutionSubmitter:
        """Queue cube-loader execution requests until the test releases them."""

        def __init__(self) -> None:
            """Create an empty execution request queue."""

            self.queue: list[
                tuple[TaskRequest[object], ManualTaskHandle[object], CancellationToken]
            ] = []

        def submit(
            self,
            request: TaskRequest[object],
            *,
            cancellation: CancellationToken,
        ) -> ManualTaskHandle[object]:
            """Queue one request and return a manually completed handle."""

            handle: ManualTaskHandle[object] = ManualTaskHandle(request)
            self.queue.append((request, handle, cancellation))
            return handle

        def run_all(self) -> None:
            """Run queued requests in submission order, including continuations."""

            while self.queue:
                request, handle, cancellation = self.queue.pop(0)
                handle.complete_success(request.work(cancellation))

    class _FakeCubeLoadService:
        """Return deterministic cube load DTOs without disk or network access."""

        def load_cube_definition(self, cube_id):
            """Return one loaded cube definition."""

            return types.SimpleNamespace(
                cube_id=cube_id,
                version="1.0.0",
                display_name=f"{cube_id} Display",
                graph={"nodes": {}},
                ui_payload=None,
            )

        def build_loaded_cube_runtime(
            self,
            cube_id,
            alias_name,
            *,
            buffer_patch,
            runtime_state,
            loaded_cube_definition,
        ):
            """Return one loaded runtime DTO."""

            cube_definition = loaded_cube_definition.graph
            cube_buffer = dict(buffer_patch or {})
            cube_state = CubeState(
                cube_id=cube_id,
                version="1.0.0",
                alias=alias_name,
                original_cube=cube_definition,
                buffer=cube_buffer,
                display_name=loaded_cube_definition.display_name,
            )
            ui_payload = {"node_behavior_runtime": runtime_state}
            cube_state.ui = ui_payload
            return types.SimpleNamespace(
                cube_id=cube_id,
                version="1.0.0",
                display_name=loaded_cube_definition.display_name,
                cube_definition=cube_definition,
                cube_buffer=cube_buffer,
                cube_state=cube_state,
                ui_payload=ui_payload,
            )

    class FakeTabItem:
        """Track one cube-tab route key."""

        def __init__(self, key):
            """Store the initial route key."""

            self._key = key
            self.text = ""

        def routeKey(self):
            """Return the route key."""

            return self._key

        def setRouteKey(self, new):
            """Update the route key."""

            self._key = new

    class FakeCubeStack:
        """Minimal cube stack used by the loader."""

        def __init__(self, initial_key):
            """Create one stack with a single placeholder tab."""

            self.items = [FakeTabItem(initial_key)]
            self.itemMap = {initial_key: self.items[0]}
            self._current = 0

        def setTabText(self, index, text):
            """Record tab text."""

            self.items[index].text = text

        def setTabPresentation(
            self,
            index,
            *,
            primary_text,
            secondary_text,
            tooltip_text,
        ):
            """Record complete cube tab presentation."""

            self.items[index].text = primary_text
            self.items[index].secondary_text = secondary_text
            self.items[index].tooltip_text = tooltip_text

        def setTabIcon(self, _index, _icon):
            """Accept tab icon updates."""

        def tabItem(self, index):
            """Return one tab item."""

            return self.items[index]

        def setCurrentIndex(self, index):
            """Record the active tab index."""

            self._current = index

        def count(self):
            """Return the tab count."""

            return len(self.items)

    class FakeEditorPanel:
        """Minimal editor-panel reveal target."""

        def __init__(self):
            """Initialize reveal tracking."""

            self.scrolled_to = None

        def scroll_to_cube(self, alias, animated=True):
            """Record a scroll request."""

            _ = animated
            self.scrolled_to = alias

        def reveal_new_cube(self, route_key):
            """Record a reveal request."""

            self.scrolled_to = route_key

    class FakeWorkflowSessionService:
        """Provide two workflows and active-workflow state."""

        def __init__(self):
            """Create workflow A and B."""

            self.active_workflow_id = "wfA"
            self.workflows = {"wfA": WorkflowState(), "wfB": WorkflowState()}

    class FakeMainWindow:
        """Bundle loader collaborators."""

        def __init__(self):
            """Create fake shell collaborators."""

            self.workflow_session_service = FakeWorkflowSessionService()
            self.cube_load_service = _FakeCubeLoadService()
            self.cube_icon_factory = types.SimpleNamespace(
                icon_for_cube=lambda **_kwargs: "resolved-icon-token"
            )
            self.cube_stack_service = types.SimpleNamespace(
                resolve_unique_alias=lambda _workflow, alias: alias,
                apply_cube_addition=lambda workflow, _cube_id, alias, cube_state: (
                    workflow.cubes.__setitem__(alias, cube_state)
                ),
                apply_reordered_aliases=lambda workflow, new_order: setattr(
                    workflow,
                    "stack_order",
                    list(new_order),
                ),
            )
            self.cube_stacks = {
                "wfA": FakeCubeStack("loading:Alias1"),
                "wfB": FakeCubeStack("loading:Other"),
            }
            self.editor_panels = {"wfA": FakeEditorPanel(), "wfB": FakeEditorPanel()}

        def refresh_workflow_after_cube_load(self, _workflow_id, _alias):
            """Accept editor refresh callbacks."""

        def materialize_loaded_cube_input_canvas(self, _workflow_id, _alias):
            """Accept canvas materialization callbacks."""

    main_window = FakeMainWindow()
    execution_submitter = FakeExecutionSubmitter()

    def cube_load_execution_route_factory(
        *,
        cube_load_trace_id: str,
    ) -> cube_loader.CubeLoadExecutionRoute:
        """Return a queued route for this regression test."""

        _ = cube_load_trace_id
        return cube_loader.CubeLoadExecutionRoute(
            submitter=execution_submitter,
            close=lambda: None,
        )

    callbacks = cube_loader.CubeLoadUiCallbacks(
        workflow_session_service=main_window.workflow_session_service,
        cube_stacks=main_window.cube_stacks,
        editor_panels=main_window.editor_panels,
        cube_load_service=main_window.cube_load_service,
        cube_stack_service=main_window.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            main_window.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=main_window.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=lambda _loaded_cube, _alias_name: (
            NodeBehaviorRuntimeState()
        ),
        cube_icon_factory=main_window.cube_icon_factory,
        cube_load_execution_route_factory=cube_load_execution_route_factory,
    )

    cube_loader.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    main_window.workflow_session_service.active_workflow_id = "wfB"
    execution_submitter.run_all()
    FakeQTimer.run_all()

    workflow_a = main_window.workflow_session_service.workflows["wfA"]
    workflow_b = main_window.workflow_session_service.workflows["wfB"]

    assert "Alias1" in workflow_a.cubes, "Cube should be added to original workflow"
    assert workflow_b.cubes == {}, "Other workflow must remain untouched"
    assert workflow_a.stack_order == ["Alias1"], "Stack order must persist per-tab"
    assert main_window.cube_stacks["wfA"].tabItem(0).routeKey() == "Alias1"
