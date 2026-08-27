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

"""Test settings-route generation availability contracts."""

from __future__ import annotations


from substitute.presentation.shell.main_window_workflow_route_adapter import (
    MainWindowWorkflowRouteAdapter,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)

from .support import (
    _availability_view,
)


def test_settings_route_disables_new_generation_and_redundant_skip_action() -> None:
    """Settings route should keep Stop routed while redundant normal Skip is disabled."""

    view = _availability_view(
        route=SETTINGS_WORKSPACE_ROUTE,
        queue_active=True,
        queue_cancellable=True,
    )

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": False,
            "can_skip": False,
            "can_stop": True,
            "can_show_queue": True,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [True]


def test_workflow_route_without_cubes_disables_new_generation_action() -> None:
    """Empty workflow routes should not allow new generation work."""

    view = _availability_view(route="workflow-a", cube_aliases=())

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": False,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": False,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [True]


def test_workflow_route_allows_generation_when_backend_is_ready() -> None:
    """Workflow route should allow Generate when backend and continuous state allow it."""

    view = _availability_view(route="workflow-a")

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": True,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": False,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [True]


def test_empty_workflow_route_keeps_stop_available_without_redundant_skip() -> None:
    """Empty workflows should keep Stop while normal Skip has no next queued work."""

    view = _availability_view(
        route="workflow-a",
        cube_aliases=(),
        queue_active=True,
        queue_cancellable=True,
    )

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": False,
            "can_skip": False,
            "can_stop": True,
            "can_show_queue": True,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [True]


def test_empty_workflow_route_keeps_continuous_skip_and_stop_available() -> None:
    """Empty workflows should not suppress active continuous-generation controls."""

    view = _availability_view(
        route="workflow-a",
        cube_aliases=(),
        continuous_active=True,
    )

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": True,
            "can_skip": True,
            "can_stop": True,
            "can_show_queue": False,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [True]


def test_workflow_route_adapter_refreshes_generation_availability() -> None:
    """Returning to a workflow route should refresh Generate availability."""

    view = _availability_view(route=SETTINGS_WORKSPACE_ROUTE)

    MainWindowWorkflowRouteAdapter(view).set_active_workspace_route("workflow-a")

    assert view._active_workspace_route == "workflow-a"
    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": True,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": False,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [True]
