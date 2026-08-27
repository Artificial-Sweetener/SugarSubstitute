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

"""Cube-stack reorder, removal, and bypass contracts."""

from __future__ import annotations

from types import SimpleNamespace


from substitute.application.cubes import (
    CubeStackService,
)


from tests.presentation.shell.cube_actions.support import (
    _CubeStack,
    _import_stack_module,
    _stack_actions,
    _surface_refresher,
)


def test_cube_stack_reorder_and_remove_delegate_to_service_apply_methods() -> None:
    """Reorder and remove flows should call the synchronized stack service helpers once."""

    mod = _import_stack_module()
    service_calls: list[tuple[str, object]] = []
    workflow = SimpleNamespace(cubes={"New": object()}, stack_order=["New"])
    active_stack = SimpleNamespace(
        count=lambda: 1,
        tabItem=lambda _index: SimpleNamespace(routeKey=lambda: "New"),
        removeTab=lambda index: service_calls.append(("remove_tab", index)),
    )
    view = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            remove_cube=lambda alias: service_calls.append(("panel_remove", alias))
        ),
        active_cube_stack=active_stack,
        cube_stack_service=SimpleNamespace(
            apply_reordered_aliases=lambda workflow_state, new_order: (
                service_calls.append(("reorder", (new_order, workflow_state)))
            ),
            apply_cube_removal=lambda workflow_state, alias_name: service_calls.append(
                (
                    "remove",
                    (alias_name, workflow_state),
                )
            ),
        ),
        get_active_workflow=lambda: workflow,
        active_workflow_surface_refresher=_surface_refresher(
            lambda: service_calls.append(("refresh", None))
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_move_finished()
    actions.on_cube_close_requested(0)

    assert ("reorder", (["New"], workflow)) in service_calls
    assert ("remove", ("New", workflow)) in service_calls
    assert ("panel_remove", "New") in service_calls


def test_cube_bypass_toggle_updates_state_and_refreshes_active_surfaces() -> None:
    """Bypass toggle should go through service and refresh stack/editor presentation."""

    mod = _import_stack_module()
    stack = _CubeStack()
    stack.insertTab(0, routeKey="Active")
    stack.insertTab(1, routeKey="Muted")
    workflow = SimpleNamespace(
        cubes={
            "Active": SimpleNamespace(bypassed=False),
            "Muted": SimpleNamespace(bypassed=False),
        },
        stack_order=["Active", "Muted"],
    )
    calls: list[tuple[str, object]] = []

    class _InvalidationService:
        """Record workflow surface invalidation calls."""

        def mark_dirty(
            self,
            workflow_id: str,
            surfaces: object,
            reason: object,
        ) -> None:
            """Record one dirty request."""

            calls.append(("dirty", (workflow_id, surfaces, reason)))

    view = SimpleNamespace(
        active_cube_stack=stack,
        active_editor_panel=SimpleNamespace(
            refresh_cube_header=lambda alias: calls.append(("header", alias))
        ),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-a"),
        workflow_surface_invalidation_service=_InvalidationService(),
        cube_stack_service=CubeStackService(),
        get_active_workflow=lambda: workflow,
        active_workflow_surface_refresher=_surface_refresher(
            lambda: calls.append(("refresh", None))
        ),
    )
    actions = _stack_actions(mod, view)

    actions.on_cube_bypass_toggle_requested("Muted")

    assert workflow.cubes["Muted"].bypassed is True
    assert stack.bypassed_updates == [(1, True)]
    assert ("header", "Muted") in calls
    assert ("refresh", None) in calls
    dirty_reasons = [
        payload[2]
        for name, payload in calls
        if name == "dirty" and isinstance(payload, tuple)
    ]
    assert mod.WorkflowInvalidationReason.CUBE_BYPASS_CHANGED in dirty_reasons
