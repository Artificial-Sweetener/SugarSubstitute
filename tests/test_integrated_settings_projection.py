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

"""Contract tests for projecting integrated Settings into the shell workspace."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.generation import GenerationQueueStateChange
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.shell_chrome_controller import ShellChromeController
from substitute.presentation.shell.settings_route_controller import (
    SettingsRouteController,
)
from substitute.presentation.shell.main_window_workflow_route_adapter import (
    MainWindowWorkflowRouteAdapter,
)
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)


class _Signal:
    """Signal double that records and emits connected callbacks."""

    def __init__(self) -> None:
        """Create an empty signal double."""

        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke connected callbacks with signal arguments."""

        for callback in self._callbacks:
            if callable(callback):
                callback(*args)


class _Splitter:
    """Splitter double that records size changes."""

    def __init__(self, sizes: list[int]) -> None:
        """Create a splitter with mutable sizes."""

        self._sizes = sizes
        self.set_sizes_calls: list[list[int]] = []

    def sizes(self) -> list[int]:
        """Return current splitter sizes."""

        return list(self._sizes)

    def setSizes(self, sizes: list[int]) -> None:
        """Record and apply splitter sizes."""

        self._sizes = list(sizes)
        self.set_sizes_calls.append(list(sizes))


class _StackContainer:
    """Stacked container double recording width and current-widget changes."""

    def __init__(self, width: int, calls: list[str]) -> None:
        """Create a stack container with one current width."""

        self._width = width
        self._calls = calls
        self.fixed_widths: list[int] = []

    def width(self) -> int:
        """Return current width."""

        return self._width

    def setFixedWidth(self, width: int) -> None:
        """Record fixed width changes."""

        self._width = width
        self.fixed_widths.append(width)
        self._calls.append(f"stack:width:{width}")

    def setCurrentWidget(self, widget: object) -> None:
        """Record widget projection."""

        self._calls.append(f"stack:set:{id(widget)}")


class _WidgetVisibility:
    """Widget double recording visibility changes."""

    def __init__(self, calls: list[str]) -> None:
        """Create a visible widget double."""

        self._calls = calls
        self.hidden = False

    def hide(self) -> None:
        """Record hidden state."""

        self.hidden = True
        self._calls.append("canvas:hide")

    def show(self) -> None:
        """Record visible state."""

        self.hidden = False
        self._calls.append("canvas:show")


class _RouteStack:
    """Route-stack double recording selected shell workspace pages."""

    def __init__(self, calls: list[str]) -> None:
        """Create an empty route-stack recorder."""

        self._calls = calls
        self.current_widget: object | None = None

    def setCurrentWidget(self, widget: object) -> None:
        """Record the selected route page."""

        self.current_widget = widget
        self._calls.append(f"route:set:{id(widget)}")


class _OrbActionCluster:
    """Under-orb action cluster double recording route visibility."""

    def __init__(self) -> None:
        """Create a visible route-chrome double."""

        self.visible = True
        self.visible_calls: list[bool] = []

    def setVisible(self, visible: bool) -> None:
        """Record whether the route chrome should be visible."""

        self.visible = visible
        self.visible_calls.append(visible)


class _SettingsToolbarSearchBox:
    """Toolbar Settings search double recording route visibility."""

    def __init__(self) -> None:
        """Create a hidden Settings toolbar search double."""

        self.visible = False
        self.visible_calls: list[bool] = []
        self.searchQueryChanged = _Signal()
        self.search_text_calls: list[str] = []

    def setVisible(self, visible: bool) -> None:
        """Record whether Settings search should be visible."""

        self.visible = visible
        self.visible_calls.append(visible)

    def set_search_text(self, text: str) -> None:
        """Record mirrored panel query text."""

        self.search_text_calls.append(text)


class _AppOrbMenu:
    """App-orb menu double recording workflow file command availability."""

    def __init__(self) -> None:
        """Create an empty availability recorder."""

        self.file_action_enabled_calls: list[bool] = []

    def set_workflow_file_actions_enabled(self, enabled: bool) -> None:
        """Record workflow file command availability."""

        self.file_action_enabled_calls.append(enabled)


class _SettingsPanel:
    """Settings panel double exposing query synchronization endpoints."""

    def __init__(self, query: str) -> None:
        """Create a panel with one initial query value."""

        self._query = query
        self.searchQueryChanged = _Signal()
        self.query_calls: list[str] = []

    def search_query(self) -> str:
        """Return the current panel query."""

        return self._query

    def set_search_query(self, query: str) -> None:
        """Record one query request from toolbar chrome."""

        self._query = query
        self.query_calls.append(query)


def _settings_controller(view: object) -> SettingsRouteController:
    """Return a Settings controller wired to shell adapter methods."""

    setattr(view, "shell_chrome_controller", ShellChromeController(view))
    if not hasattr(view, "generation_queue_controller"):
        setattr(
            view, "generation_queue_controller", SimpleNamespace(panel_visible=False)
        )
    if not hasattr(view, "cube_stack_presentation_controller"):

        def set_workflow_route_active(active: bool) -> None:
            """Project route activity through the presentation owner test port."""

            material = getattr(view, "workspace_body_material_surface", None)
            set_region = getattr(material, "set_cube_stack_region_widget", None)
            if callable(set_region):
                set_region(
                    getattr(view, "cube_stack_container", None) if active else None
                )
            button = getattr(view, "cubeStackModeButton", None)
            set_enabled = getattr(button, "setEnabled", None)
            if callable(set_enabled):
                set_enabled(active)

        setattr(
            view,
            "cube_stack_presentation_controller",
            SimpleNamespace(set_workflow_route_active=set_workflow_route_active),
        )
    if not hasattr(view, "generation_action_controller"):
        setattr(view, "generation_action_controller", GenerationActionController(view))
    return SettingsRouteController(view, error_presenter=None)


class _OverrideMenuController:
    """Override popup controller double recording close requests."""

    def __init__(self) -> None:
        """Create a controller with no close requests."""

        self.close_calls = 0

    def close_menu_if_open(self) -> bool:
        """Record one request to close the override popup."""

        self.close_calls += 1
        return True


class _Button:
    """Button double recording enabled state."""

    def __init__(self) -> None:
        """Create an enabled button double."""

        self.enabled: list[bool] = []
        self.tooltips: list[str] = []

    def setEnabled(self, enabled: bool) -> None:
        """Record enabled state."""

        self.enabled.append(enabled)

    def setToolTip(self, tooltip: str) -> None:
        """Record tooltip text."""

        self.tooltips.append(tooltip)


class _CubeStack:
    """Cube stack double recording compact calls."""

    def __init__(self) -> None:
        """Create a compact-recording cube stack."""

        self.compact_values: list[bool] = []

    def setCompact(self, compact: bool) -> None:
        """Record compact state changes."""

        self.compact_values.append(compact)


class _GenerationActionCluster:
    """Generation cluster double recording titlebar action availability."""

    def __init__(self) -> None:
        """Create an empty availability recorder."""

        self.availability_calls: list[dict[str, bool]] = []
        self.queue_badge_count_calls: list[int] = []
        self.queue_segment_visible_calls: list[bool] = []
        self.presentation_calls: list[GenerationActionPresentation] = []
        self.batch_count = 1

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one complete generation action presentation."""

        self.presentation_calls.append(presentation)
        self.availability_calls.append(
            {
                "can_generate": presentation.play_enabled,
                "can_skip": presentation.skip_enabled,
                "can_stop": presentation.stop_enabled,
                "can_show_queue": presentation.queue_primary_enabled,
            }
        )
        self.queue_badge_count_calls.append(presentation.queue_badge_count)
        self.queue_segment_visible_calls.append(presentation.queue_segment_visible)

    def set_batch_count(self, value: int) -> None:
        """Record the titlebar batch count value."""

        self.batch_count = max(1, value)

    def effective_batch_count(self) -> int:
        """Return the normal-generation batch count for controller bindings."""

        return self.batch_count


class _GenerationController:
    """Generation controller double exposing continuous mode state."""

    def __init__(self, *, continuous_active: bool) -> None:
        """Create a controller with one continuous-active value."""

        self.is_continuous_active = continuous_active


class _GenerationQueueService:
    """Generation queue double exposing active and cancellable job state."""

    def __init__(
        self,
        *,
        active: bool,
        cancellable: bool,
        visible_jobs: tuple[object, ...] | None = None,
    ) -> None:
        """Create a queue service with stable availability state."""

        self._active = active
        self._cancellable = cancellable
        self._visible_jobs = (
            visible_jobs
            if visible_jobs is not None
            else (object(),)
            if active or cancellable
            else ()
        )
        self.jobs_calls = 0

    def has_active_job(self) -> bool:
        """Return whether a queue job is currently active."""

        return self._active

    def has_cancellable_jobs(self) -> bool:
        """Return whether the queue has cancellable work."""

        return self._cancellable

    def jobs(self) -> tuple[object, ...]:
        """Return visible queue rows for queue-button availability."""

        self.jobs_calls += 1
        return self._visible_jobs


def _availability_view(
    *,
    route: str,
    active_workflow_id: str = "workflow-a",
    cube_aliases: tuple[str, ...] = ("Cube",),
    backend_state: str = "ready",
    continuous_active: bool = False,
    queue_active: bool = False,
    queue_cancellable: bool = False,
    queue_panel_visible: bool = False,
    queue_visible_jobs: tuple[object, ...] | None = None,
) -> SimpleNamespace:
    """Build a lightweight MainWindow double for generation availability tests."""

    workflow_cubes = {alias: object() for alias in cube_aliases}
    view = SimpleNamespace(
        generationActionCluster=_GenerationActionCluster(),
        _backend_state=backend_state,
        _active_workspace_route=route,
        workflow_session_service=SimpleNamespace(
            active_workflow_id=active_workflow_id,
            workflows={
                active_workflow_id: SimpleNamespace(cubes=workflow_cubes),
            },
        ),
        workspace_generation_controller=_GenerationController(
            continuous_active=continuous_active,
        ),
        generation_job_queue_service=_GenerationQueueService(
            active=queue_active,
            cancellable=queue_cancellable,
            visible_jobs=queue_visible_jobs,
        ),
        sidePanelHost=SimpleNamespace(
            is_queue_panel_visible=lambda: queue_panel_visible,
        ),
    )
    view.shell_chrome_controller = ShellChromeController(view)
    view.generation_queue_controller = SimpleNamespace(
        panel_visible=queue_panel_visible
    )
    view.generation_action_controller = GenerationActionController(view)
    return view


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
    canvas_tabs_container = _WidgetVisibility(calls)
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
        canvas_tabs_container=canvas_tabs_container,
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
    assert canvas_tabs_container.hidden is False
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


def test_generation_queue_observer_uses_supplied_jobs_without_projection() -> None:
    """Queue observer path should not ask the queue service to project jobs again."""

    view = _availability_view(
        route="workflow-a",
        queue_active=True,
        queue_cancellable=True,
    )
    view.generation_action_controller.handle_generation_queue_state_changed(
        GenerationQueueStateChange(
            jobs=(),
            change_kind="progress",
            changed_job_id="job-1",
        ),
    )

    assert view.generation_job_queue_service.jobs_calls == 0
    assert view.generationActionCluster.presentation_calls[-1].queue_segment_visible


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
        canvas_tabs_container=_WidgetVisibility(calls),
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
    assert view.canvas_tabs_container.hidden is False
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


def test_settings_toolbar_search_wires_to_panel_query_state() -> None:
    """Toolbar Settings search should mirror and update panel-owned query state."""

    search_box = _SettingsToolbarSearchBox()
    panel = _SettingsPanel("credential")
    view = SimpleNamespace(
        settingsToolbarSearchBox=search_box,
        settings_workspace_panel=panel,
    )

    SettingsRouteController(
        view, error_presenter=None
    ).connect_settings_toolbar_search()

    assert search_box.search_text_calls == ["credential"]

    search_box.searchQueryChanged.emit("thumbnail")
    panel.searchQueryChanged.emit("server")

    assert panel.query_calls == ["thumbnail"]
    assert search_box.search_text_calls == ["credential", "server"]


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
        canvas_tabs_container=_WidgetVisibility(calls),
        cubeStackModeButton=_Button(),
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_region_widget=lambda widget: material_regions.append(widget)
        ),
        workspace_route_container=route_stack,
        workflow_workspace_page=workflow_page,
    )

    _settings_controller(view).show_workflow_workspace()

    assert view.canvas_tabs_container.hidden is False
    assert view.splitter.set_sizes_calls == []
    assert view.cube_stack_container.fixed_widths == []
    assert material_regions == [cube_stack_container]
    assert route_stack.current_widget is workflow_page


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


def test_visible_queue_panel_removes_titlebar_queue_segment() -> None:
    """Full queue panel visibility should hide the redundant titlebar queue segment."""

    view = _availability_view(
        route="workflow-a",
        queue_panel_visible=True,
        queue_visible_jobs=(object(),),
    )

    view.generation_action_controller.apply_generation_action_availability()

    assert view.generationActionCluster.availability_calls == [
        {
            "can_generate": True,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": True,
        }
    ]
    assert view.generationActionCluster.queue_segment_visible_calls == [False]


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
