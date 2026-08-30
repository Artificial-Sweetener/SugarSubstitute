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

"""Test settings-route workspace projection contracts."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.workflows.cube_stack_view import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)

from .support import (
    _AppOrbMenu,
    _Button,
    _GenerationActionCluster,
    _GenerationController,
    _GenerationQueueService,
    _OrbActionCluster,
    _OverrideMenuController,
    _RouteStack,
    _SettingsToolbarSearchBox,
    _Splitter,
    _StackContainer,
    _WidgetVisibility,
    _settings_controller,
)


def test_project_settings_workspace_uses_settings_widgets_without_workflow_mutation() -> (
    None
):
    """Settings projection should switch routes without changing workflow geometry."""

    calls: list[str] = []
    material_regions: list[object | None] = []
    active_workflow_id = "wf-a"
    settings_page = object()
    settings_panel = SimpleNamespace(
        set_route_active=lambda active: calls.append(f"settings:active:{active}")
    )
    manager = SimpleNamespace(
        clear_toolbar_override_controls=lambda: calls.append("overrides:clear")
    )
    splitter = _Splitter([640, 360])
    cube_stack_container = _StackContainer(CUBE_STACK_COMPACT_WIDTH, calls)
    canvas_host_container = _WidgetVisibility(calls)
    cube_mode_button = _Button()
    orb_action_cluster = _OrbActionCluster()
    settings_toolbar_search = _SettingsToolbarSearchBox()
    app_orb_menu = _AppOrbMenu()
    override_menu_controller = _OverrideMenuController()
    availability_cluster = _GenerationActionCluster()
    route_stack = _RouteStack(calls)
    view = SimpleNamespace(
        active_override_manager=manager,
        workflow_session_service=SimpleNamespace(active_workflow_id=active_workflow_id),
        workflow_tabbar=SimpleNamespace(
            clear_selection=lambda: calls.append("tab:clear")
        ),
        cube_stack_container=cube_stack_container,
        editor_panel_container=SimpleNamespace(
            setCurrentWidget=lambda widget: calls.append(
                f"editor:set:{widget is settings_panel}"
            )
        ),
        splitter=splitter,
        canvas_host_container=canvas_host_container,
        cubeStackModeButton=cube_mode_button,
        orbActionCluster=orb_action_cluster,
        settingsToolbarSearchBox=settings_toolbar_search,
        appOrbMenuButton=app_orb_menu,
        override_dropdown_btn=SimpleNamespace(
            _menu_controller=override_menu_controller
        ),
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_region_widget=lambda widget: material_regions.append(widget)
        ),
        workspace_route_container=route_stack,
        settings_workspace_page=settings_page,
        settings_workspace_panel=settings_panel,
        contextSearchBox=SimpleNamespace(hide=lambda: calls.append("search:hide")),
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: calls.append("position")
        ),
        editor_busy=SimpleNamespace(
            refresh_active_surface=lambda: calls.append("busy:refresh")
        ),
        generationActionCluster=availability_cluster,
        _backend_state="ready",
        workspace_generation_controller=_GenerationController(
            continuous_active=False,
        ),
        generation_job_queue_service=_GenerationQueueService(
            active=False,
            cancellable=False,
        ),
    )
    _settings_controller(view).project_settings_workspace()

    assert view._active_workspace_route == SETTINGS_WORKSPACE_ROUTE
    assert view.workflow_session_service.active_workflow_id == active_workflow_id
    assert route_stack.current_widget is settings_page
    assert canvas_host_container.hidden is False
    assert splitter.set_sizes_calls == []
    assert cube_stack_container.fixed_widths == []
    assert cube_mode_button.enabled == [False]
    assert orb_action_cluster.visible is False
    assert orb_action_cluster.visible_calls == [False]
    assert settings_toolbar_search.visible is True
    assert settings_toolbar_search.visible_calls == [True]
    assert app_orb_menu.file_action_enabled_calls == [False]
    assert override_menu_controller.close_calls == 1
    assert material_regions == [None]
    assert availability_cluster.availability_calls == [
        {
            "can_generate": False,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": False,
        }
    ]
    assert calls == [
        "overrides:clear",
        "tab:clear",
        f"route:set:{id(settings_page)}",
        "settings:active:True",
        "search:hide",
        "position",
        "busy:refresh",
    ]


def test_workspace_route_helpers_switch_pages_without_geometry_mutation() -> None:
    """Route helpers should preserve geometry while updating route chrome."""

    calls: list[str] = []
    material_regions: list[object | None] = []
    workflow_page = object()
    settings_page = object()
    route_stack = _RouteStack(calls)
    cube_mode_button = _Button()
    cube_stack_container = _StackContainer(CUBE_STACK_COMPACT_WIDTH, calls)
    orb_action_cluster = _OrbActionCluster()
    settings_toolbar_search = _SettingsToolbarSearchBox()
    app_orb_menu = _AppOrbMenu()
    override_menu_controller = _OverrideMenuController()
    view = SimpleNamespace(
        splitter=_Splitter([600, 400]),
        cube_stack_container=cube_stack_container,
        canvas_host_container=_WidgetVisibility(calls),
        cubeStackModeButton=cube_mode_button,
        orbActionCluster=orb_action_cluster,
        settingsToolbarSearchBox=settings_toolbar_search,
        appOrbMenuButton=app_orb_menu,
        override_dropdown_btn=SimpleNamespace(
            _menu_controller=override_menu_controller
        ),
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_region_widget=lambda widget: material_regions.append(widget)
        ),
        workspace_route_container=route_stack,
        workflow_workspace_page=workflow_page,
        settings_workspace_page=settings_page,
    )

    controller = _settings_controller(view)
    controller.show_settings_workspace()
    controller.show_workflow_workspace()

    assert route_stack.current_widget is workflow_page
    assert view.splitter.set_sizes_calls == []
    assert view.cube_stack_container.fixed_widths == []
    assert view.canvas_host_container.hidden is False
    assert cube_mode_button.enabled == [False, True]
    assert orb_action_cluster.visible is True
    assert orb_action_cluster.visible_calls == [False, True]
    assert settings_toolbar_search.visible is False
    assert settings_toolbar_search.visible_calls == [True, False]
    assert app_orb_menu.file_action_enabled_calls == [False, True]
    assert override_menu_controller.close_calls == 1
    assert material_regions == [None, cube_stack_container]
    assert calls == [
        f"route:set:{id(settings_page)}",
        f"route:set:{id(workflow_page)}",
    ]


def test_settings_route_projection_does_not_restore_workflow_geometry() -> None:
    """Leaving Settings should only switch route pages because geometry is unchanged."""

    calls: list[str] = []
    workflow_page = object()
    route_stack = _RouteStack(calls)
    material_regions: list[object | None] = []
    cube_stack_container = _StackContainer(CUBE_STACK_EXPANDED_WIDTH, calls)
    view = SimpleNamespace(
        splitter=_Splitter([610, 390]),
        cube_stack_container=cube_stack_container,
        canvas_host_container=_WidgetVisibility(calls),
        cubeStackModeButton=_Button(),
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_region_widget=lambda widget: material_regions.append(widget)
        ),
        workspace_route_container=route_stack,
        workflow_workspace_page=workflow_page,
    )

    _settings_controller(view).show_workflow_workspace()

    assert view.canvas_host_container.hidden is False
    assert view.splitter.set_sizes_calls == []
    assert view.cube_stack_container.fixed_widths == []
    assert material_regions == [cube_stack_container]
    assert route_stack.current_widget is workflow_page
