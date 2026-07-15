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

"""Own loaded-cube shell surface refresh helpers."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from time import perf_counter
from typing import TypeVar, cast

from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeStackProtocol,
    CubeTabIconResolver,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info, log_timing

_LOGGER = get_logger("presentation.shell.loaded_cube_surface_controller")
_CubeLoadCallbacksT = TypeVar("_CubeLoadCallbacksT")


class WorkspaceLoadedCubeSurfaceActions:
    """Own loaded-cube shell surface refresh and activation actions."""

    def __init__(
        self,
        *,
        cube_view: object,
        workflow_workspace_view: object,
        workflow_workspace: object,
        schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
        schedule_indicator_realign: Callable[[Callable[[], None]], None],
    ) -> None:
        """Store shell collaborators and scheduling adapters."""

        self._cube_view = cube_view
        self._workflow_workspace_view = workflow_workspace_view
        self._workflow_workspace = workflow_workspace
        self._schedule_deferred_rebuild = schedule_deferred_rebuild
        self._schedule_indicator_realign = schedule_indicator_realign

    def refresh_workflow_after_cube_load(
        self,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Refresh active shell surfaces after a target workflow cube load."""

        refresh_workflow_after_cube_load_for_view(
            cube_view=self._cube_view,
            workflow_workspace_view=self._workflow_workspace_view,
            workflow_workspace=self._workflow_workspace,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            schedule_deferred_rebuild=self._schedule_deferred_rebuild,
            activate_loaded_cube=self.activate_loaded_cube,
        )

    def refresh_workflow_after_cube_load_async(
        self,
        workflow_id: str,
        cube_alias: str,
        on_complete: Callable[[], None],
    ) -> None:
        """Refresh loaded-cube surfaces asynchronously after cube loading."""

        refresh_workflow_after_cube_load_for_view_async(
            cube_view=self._cube_view,
            workflow_workspace_view=self._workflow_workspace_view,
            workflow_workspace=self._workflow_workspace,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            schedule_deferred_rebuild=self._schedule_deferred_rebuild,
            activate_loaded_cube=self.activate_loaded_cube,
            on_complete=on_complete,
        )

    def refresh_loaded_cube_surface(
        self,
        workflow_id: str,
        cube_alias: str,
        *,
        phase: str = "complete",
    ) -> bool:
        """Refresh editor and stack presentation for one loaded cube."""

        _ = phase
        return refresh_loaded_cube_surface_for_view(
            cube_view=self._cube_view,
            workflow_workspace_view=self._workflow_workspace_view,
            workflow_workspace=self._workflow_workspace,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            schedule_deferred_rebuild=self._schedule_deferred_rebuild,
        )

    def refresh_loaded_cube_surface_async(
        self,
        workflow_id: str,
        cube_alias: str,
        on_complete: Callable[[bool], None],
        *,
        wait_for_complete: bool = False,
    ) -> None:
        """Refresh one loaded-cube surface from asynchronous loader callbacks."""

        refresh_loaded_cube_surface_for_view_async(
            cube_view=self._cube_view,
            workflow_workspace_view=self._workflow_workspace_view,
            workflow_workspace=self._workflow_workspace,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            on_complete=on_complete,
            wait_for_complete=wait_for_complete,
            schedule_deferred_rebuild=self._schedule_deferred_rebuild,
        )

    def mark_loaded_cube_surface_stale(
        self,
        workflow_id: str,
        cube_alias: str,
        *,
        reason: str,
    ) -> None:
        """Mark one active editor cube surface stale before a refresh."""

        mark_loaded_cube_surface_stale(
            self._cube_view,
            workflow_id,
            cube_alias,
            reason=reason,
        )

    def activate_loaded_cube(
        self,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Synchronize stack selection and editor navigation for one loaded cube."""

        activate_loaded_cube_surface(
            self._cube_view,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            schedule_indicator_realign=self._schedule_indicator_realign,
        )


def build_cube_load_ui_callbacks_for_view(
    *,
    cube_view: object,
    callbacks_type: Callable[..., _CubeLoadCallbacksT],
    materialize_loaded_cube_input_canvas: Callable[[str, str], None],
    refresh_workflow_after_cube_load: Callable[[str, str], None],
    prepare_node_behavior_runtime: Callable[[object, str], object],
    refresh_loaded_cube_surface: Callable[..., bool],
    activate_loaded_cube: Callable[[str, str], None],
    refresh_workflow_after_cube_load_async: Callable[
        [str, str, Callable[[], None]], None
    ],
    refresh_loaded_cube_surface_async: Callable[..., None],
    cube_load_execution_route_factory: Callable[..., object],
) -> _CubeLoadCallbacksT:
    """Assemble explicit cube-loader callbacks from shell collaborators."""

    workflow_session_service = getattr(cube_view, "workflow_session_service", None)
    active_cube_stack = getattr(cube_view, "active_cube_stack", None)
    active_editor_panel = getattr(cube_view, "active_editor_panel", None)
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_callbacks_built",
        active_workflow_id=getattr(workflow_session_service, "active_workflow_id", ""),
        workflow_ids=list(getattr(workflow_session_service, "workflows", {}) or {}),
        cube_stack_ids=list(getattr(cube_view, "cube_stacks", {}) or {}),
        editor_panel_ids=list(getattr(cube_view, "editor_panels", {}) or {}),
        active_cube_stack_present=active_cube_stack is not None,
        active_editor_panel_present=active_editor_panel is not None,
    )
    return callbacks_type(
        workflow_session_service=workflow_session_service,
        cube_stacks=getattr(cube_view, "cube_stacks", {}),
        editor_panels=getattr(cube_view, "editor_panels", {}),
        cube_load_service=getattr(cube_view, "cube_load_service", None),
        cube_stack_service=getattr(cube_view, "cube_stack_service", None),
        materialize_loaded_cube_input_canvas=materialize_loaded_cube_input_canvas,
        refresh_workflow_after_cube_load=refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=prepare_node_behavior_runtime,
        cube_icon_factory=getattr(cube_view, "cube_icon_factory", None),
        refresh_loaded_cube_surface=refresh_loaded_cube_surface,
        activate_loaded_cube=activate_loaded_cube,
        refresh_workflow_after_cube_load_async=refresh_workflow_after_cube_load_async,
        refresh_loaded_cube_surface_async=refresh_loaded_cube_surface_async,
        cube_load_execution_route_factory=cube_load_execution_route_factory,
    )


def refresh_active_cube_stack_tab_for_view(
    cube_view: object,
    workflow_id: str,
    cube_alias: str,
) -> bool:
    """Reapply stack tab presentation from the current workflow cube state."""

    workflow_session_service = getattr(cube_view, "workflow_session_service", None)
    active_workflow_id = getattr(workflow_session_service, "active_workflow_id", None)
    if workflow_id != active_workflow_id:
        return False
    active_stack = getattr(cube_view, "active_cube_stack", None)
    if active_stack is None:
        return False
    get_active_workflow = getattr(cube_view, "get_active_workflow", None)
    if not callable(get_active_workflow):
        return False
    workflow = get_active_workflow()
    cubes = getattr(workflow, "cubes", {})
    if not isinstance(cubes, Mapping):
        return False
    cube_state = cubes.get(cube_alias)
    if cube_state is None:
        return False
    tab_index = cube_stack_tab_index(active_stack, cube_alias)
    if tab_index is None:
        return False
    result = CubeStackPresenter(
        icon_resolver=CubeTabIconResolver(
            cube_icon_factory=getattr(cube_view, "cube_icon_factory", None),
            fallback_icon=getattr(cube_view, "cube_tab_fallback_icon", None),
        ),
    ).apply_tab(
        cast(CubeStackProtocol, active_stack),
        tab_index,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        cube_state=cube_state,
        issue_state=getattr(cube_view, "workflow_issue_state", None),
    )
    log_info(
        _LOGGER,
        "Refreshed cube-stack tab presentation from workflow cube state",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        cube_version=getattr(cube_state, "version", ""),
        tab_index=tab_index,
        applied_presentation=result.applied_presentation,
        applied_icon=result.applied_icon,
        warning_count=len(result.warnings),
    )
    return True


def activate_loaded_cube_surface(
    cube_view: object,
    workflow_id: str,
    cube_alias: str,
    *,
    schedule_indicator_realign: Callable[[Callable[[], None]], None],
) -> None:
    """Synchronize stack selection and editor navigation for one loaded cube."""

    workflow_session_service = getattr(cube_view, "workflow_session_service", None)
    active_workflow_id = getattr(workflow_session_service, "active_workflow_id", None)
    if workflow_id != active_workflow_id:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="loaded_cube_activate_skipped_stale_workflow",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            active_workflow_id=active_workflow_id,
        )
        return
    activation_started_at = perf_counter()
    active_stack = getattr(cube_view, "active_cube_stack", None)
    active_panel = getattr(cube_view, "active_editor_panel", None)
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="loaded_cube_activate_start",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        active_stack_present=active_stack is not None,
        active_panel_present=active_panel is not None,
    )
    if active_stack is not None:
        _select_loaded_cube_stack_tab(cube_view, active_stack, cube_alias)
        realign_indicator = getattr(active_stack, "realign_indicator", None)
        if callable(realign_indicator):
            schedule_indicator_realign(
                lambda: realign_indicator(animated=False),
            )

    if active_panel is not None:
        _reveal_loaded_cube_in_editor(
            active_panel,
            workflow_id=workflow_id,
            cube_alias=cube_alias,
        )
    log_timing(
        _LOGGER,
        "Activated loaded cube",
        started_at=activation_started_at,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        level="debug",
    )


def mark_loaded_cube_surface_stale(
    cube_view: object,
    workflow_id: str,
    cube_alias: str,
    *,
    reason: str,
) -> None:
    """Mark an active editor cube section stale before definition refresh."""

    workflow_session_service = getattr(cube_view, "workflow_session_service", None)
    active_workflow_id = getattr(workflow_session_service, "active_workflow_id", None)
    if workflow_id != active_workflow_id:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="loaded_cube_stale_mark_skipped_stale_workflow",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            active_workflow_id=active_workflow_id,
            reason=reason,
        )
        return
    panel = getattr(cube_view, "active_editor_panel", None)
    coordinator = getattr(panel, "_projection_coordinator", None)
    if coordinator is None:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="loaded_cube_stale_mark_skipped_missing_coordinator",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
            active_panel_present=panel is not None,
        )
        return
    mark_stale = getattr(coordinator, "mark_cube_sections_stale", None)
    if callable(mark_stale):
        mark_stale([cube_alias], reason=reason)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="loaded_cube_surface_marked_stale",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
        )


def schedule_deferred_incremental_override_presentation_rebuild(
    *,
    workflow_session_service: object,
    workflow_id: str,
    active_manager: object,
    schedule_rebuild: Callable[[Callable[[], None]], None],
) -> None:
    """Schedule loaded-cube override presentation rebuild after state sync."""

    log_info(
        _LOGGER,
        "Scheduled deferred incremental override presentation rebuild",
        workflow_id=workflow_id,
    )

    def rebuild_if_current() -> None:
        """Rebuild incremental override presentation for the active workflow."""

        active_workflow_id = str(
            getattr(
                workflow_session_service,
                "active_workflow_id",
                "",
            )
        )
        if active_workflow_id != workflow_id:
            log_info(
                _LOGGER,
                "Skipped stale deferred incremental override presentation rebuild",
                workflow_id=workflow_id,
                active_workflow_id=active_workflow_id,
            )
            return
        phase_started_at = perf_counter()
        rebuild_menu = getattr(active_manager, "rebuild_override_menu", None)
        rebuild_controls = getattr(
            active_manager,
            "rebuild_active_override_controls",
            None,
        )
        if callable(rebuild_menu):
            rebuild_menu()
        if callable(rebuild_controls):
            rebuild_controls()
        override_controls = getattr(
            active_manager,
            "_global_override_controls",
            {},
        )
        log_timing(
            _LOGGER,
            "Rebuilt incremental override presentation",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            override_control_count=(
                len(override_controls) if isinstance(override_controls, dict) else 0
            ),
            level="debug",
        )

    schedule_rebuild(rebuild_if_current)


def refresh_incremental_loaded_cube_surface(
    *,
    cube_view: object,
    workflow_workspace_view: object,
    workflow_id: str,
    cube_alias: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
    on_complete: Callable[[], None] | None = None,
    completion_phase: str = "first_usable",
) -> bool:
    """Project one loaded cube into the active editor without a full reload."""

    active_panel = getattr(cube_view, "active_editor_panel", None)
    insert_cube_section = getattr(active_panel, "insert_cube_section", None)
    if active_panel is None or not callable(insert_cube_section):
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_incremental_refresh_unavailable",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason="missing_active_panel_or_insert_method",
            active_panel_present=active_panel is not None,
        )
        return False
    get_active_workflow = getattr(cube_view, "get_active_workflow", None)
    if not callable(get_active_workflow):
        return False
    workflow = get_active_workflow()
    cubes = getattr(workflow, "cubes", {})
    cube_state = cubes.get(cube_alias) if isinstance(cubes, Mapping) else None
    if cube_state is None:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_incremental_refresh_unavailable",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason="missing_cube_state",
            workflow_stack_order=list(getattr(workflow, "stack_order", []) or []),
            workflow_cube_aliases=list(cubes or {})
            if isinstance(cubes, Mapping)
            else [],
        )
        return False
    existing_widgets = getattr(active_panel, "cube_widgets", {})
    existing_widget = (
        existing_widgets.get(cube_alias) if isinstance(existing_widgets, dict) else None
    )
    log_info(
        _LOGGER,
        "Refreshing one loaded cube surface incrementally",
        event="frontend_update_incremental_refresh_state",
        trace_id=f"cube-update:{workflow_id}:{cube_alias}",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        cube_state_object_id=id(cube_state),
        cube_version=getattr(cube_state, "version", ""),
        buffer_object_id=id(getattr(cube_state, "buffer", None)),
        existing_widget_present=existing_widget is not None,
        existing_widget_object_id=id(existing_widget) if existing_widget else "",
        active_panel_type=type(active_panel).__name__,
    )

    def finish_after_insert() -> None:
        """Refresh dependent shell controls after editor insertion finishes."""

        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_incremental_insert_complete",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            completion_phase=completion_phase,
        )
        _refresh_override_manager_after_incremental_insert(
            workflow_workspace_view=workflow_workspace_view,
            workflow_id=workflow_id,
            schedule_deferred_rebuild=schedule_deferred_rebuild,
        )
        _refresh_dependent_controls_after_incremental_insert(workflow_workspace_view)
        if on_complete is not None:
            on_complete()

    stack_order = getattr(workflow, "stack_order", [])
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_incremental_insert_call",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        completion_phase=completion_phase,
        workflow_stack_order=list(stack_order or []),
        workflow_cube_aliases=list(cubes or {}) if isinstance(cubes, Mapping) else [],
        active_panel_type=type(active_panel).__name__,
    )
    insert_cube_section(
        cube_alias,
        cube_state,
        cube_states=cubes,
        stack_order=stack_order,
        on_complete=finish_after_insert,
        completion_phase=completion_phase,
    )
    return True


def refresh_loaded_cube_surface_for_view(
    *,
    cube_view: object,
    workflow_workspace_view: object,
    workflow_workspace: object,
    workflow_id: str,
    cube_alias: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
) -> bool:
    """Refresh active shell surfaces without changing cube activation."""

    active_workflow_id = _active_workflow_id(cube_view)
    if workflow_id != active_workflow_id:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_refresh_surface_skipped_stale_workflow",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            active_workflow_id=active_workflow_id,
        )
        return False
    refresh_started_at = perf_counter()
    refresh_active_cube_stack_tab_for_view(
        cube_view,
        workflow_id,
        cube_alias,
    )
    used_incremental = refresh_incremental_loaded_cube_surface(
        cube_view=cube_view,
        workflow_workspace_view=workflow_workspace_view,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        schedule_deferred_rebuild=schedule_deferred_rebuild,
    )
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_refresh_surface_path",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        used_incremental=used_incremental,
    )
    if not used_incremental:
        _reconcile_active_workflow_after_loaded_cube_refresh(workflow_workspace)
    log_timing(
        _LOGGER,
        "Refreshed workspace surface after cube load",
        started_at=refresh_started_at,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        level="debug",
    )
    return True


def refresh_loaded_cube_surface_for_view_async(
    *,
    cube_view: object,
    workflow_workspace_view: object,
    workflow_workspace: object,
    workflow_id: str,
    cube_alias: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
    on_complete: Callable[[bool], None],
    wait_for_complete: bool = False,
) -> None:
    """Refresh active shell surfaces and report when editor build is complete."""

    active_workflow_id = _active_workflow_id(cube_view)
    if workflow_id != active_workflow_id:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_refresh_surface_async_skipped_stale_workflow",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            active_workflow_id=active_workflow_id,
            wait_for_complete=wait_for_complete,
        )
        on_complete(False)
        return
    refresh_started_at = perf_counter()
    refresh_active_cube_stack_tab_for_view(
        cube_view,
        workflow_id,
        cube_alias,
    )

    def finish(refreshed: bool) -> None:
        """Log the async refresh result before notifying the caller."""

        if refreshed:
            log_timing(
                _LOGGER,
                "Refreshed workspace surface after cube load",
                started_at=refresh_started_at,
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                level="debug",
            )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_refresh_surface_async_finish",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            refreshed=refreshed,
            wait_for_complete=wait_for_complete,
        )
        on_complete(refreshed)

    used_incremental = refresh_incremental_loaded_cube_surface(
        cube_view=cube_view,
        workflow_workspace_view=workflow_workspace_view,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        schedule_deferred_rebuild=schedule_deferred_rebuild,
        on_complete=lambda: finish(True),
        completion_phase="complete" if wait_for_complete else "first_usable",
    )
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_refresh_surface_async_path",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        used_incremental=used_incremental,
        wait_for_complete=wait_for_complete,
    )
    log_info(
        _LOGGER,
        "Selected loaded cube surface refresh path",
        event="frontend_update_refresh_async_path",
        trace_id=f"cube-update:{workflow_id}:{cube_alias}",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        used_incremental=used_incremental,
        wait_for_complete=wait_for_complete,
    )
    if used_incremental:
        return
    _reconcile_active_workflow_after_loaded_cube_refresh(workflow_workspace)
    finish(True)


def refresh_workflow_after_cube_load_for_view(
    *,
    cube_view: object,
    workflow_workspace_view: object,
    workflow_workspace: object,
    workflow_id: str,
    cube_alias: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
    activate_loaded_cube: Callable[[str, str], None],
) -> None:
    """Refresh active shell surfaces and activate a loaded cube when refreshed."""

    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_refresh_after_load_start",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        active_workflow_id=_active_workflow_id(cube_view),
    )
    refreshed = refresh_loaded_cube_surface_for_view(
        cube_view=cube_view,
        workflow_workspace_view=workflow_workspace_view,
        workflow_workspace=workflow_workspace,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        schedule_deferred_rebuild=schedule_deferred_rebuild,
    )
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_refresh_after_load_result",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        refreshed=refreshed,
    )
    if refreshed:
        activate_loaded_cube(workflow_id, cube_alias)


def refresh_workflow_after_cube_load_for_view_async(
    *,
    cube_view: object,
    workflow_workspace_view: object,
    workflow_workspace: object,
    workflow_id: str,
    cube_alias: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
    activate_loaded_cube: Callable[[str, str], None],
    on_complete: Callable[[], None],
) -> None:
    """Refresh active shell surfaces and activate the cube after async build."""

    def finish_after_surface(refreshed: bool) -> None:
        """Activate the cube after its editor surface has finished refreshing."""

        log_debug(
            _LOGGER,
            "Cube load detail",
            event="controller_async_refresh_after_surface",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            refreshed=refreshed,
        )
        if refreshed:
            activate_loaded_cube(workflow_id, cube_alias)
        on_complete()

    log_debug(
        _LOGGER,
        "Cube load detail",
        event="controller_async_refresh_after_load_start",
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        active_workflow_id=_active_workflow_id(cube_view),
    )
    refresh_loaded_cube_surface_for_view_async(
        cube_view=cube_view,
        workflow_workspace_view=workflow_workspace_view,
        workflow_workspace=workflow_workspace,
        workflow_id=workflow_id,
        cube_alias=cube_alias,
        schedule_deferred_rebuild=schedule_deferred_rebuild,
        on_complete=finish_after_surface,
    )


def _refresh_override_manager_after_incremental_insert(
    *,
    workflow_workspace_view: object,
    workflow_id: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
) -> None:
    """Refresh override manager state after one loaded-cube editor insertion."""

    override_managers = getattr(workflow_workspace_view, "override_managers", {})
    active_manager = (
        override_managers.get(workflow_id)
        if isinstance(override_managers, Mapping)
        else None
    )
    if active_manager is None:
        return
    active_manager.sync_state_from_workflow()
    active_manager.materialize_default_overrides()
    active_manager.apply_global_overrides(use_cached_behavior_snapshot=True)
    schedule_deferred_incremental_override_presentation_rebuild(
        workflow_session_service=getattr(
            workflow_workspace_view,
            "workflow_session_service",
            None,
        ),
        workflow_id=workflow_id,
        active_manager=active_manager,
        schedule_rebuild=schedule_deferred_rebuild,
    )


def _refresh_dependent_controls_after_incremental_insert(
    workflow_workspace_view: object,
) -> None:
    """Refresh shell controls whose availability depends on cube insertion."""

    canvas_route_controller = getattr(
        workflow_workspace_view,
        "canvas_route_controller",
        None,
    )
    refresh_input_canvas_availability = getattr(
        canvas_route_controller,
        "refresh_input_canvas_availability",
        None,
    )
    if callable(refresh_input_canvas_availability):
        refresh_input_canvas_availability()
    generation_action_controller = getattr(
        workflow_workspace_view,
        "generation_action_controller",
        None,
    )
    apply_generation_action_availability = getattr(
        generation_action_controller,
        "apply_generation_action_availability",
        None,
    )
    if callable(apply_generation_action_availability):
        apply_generation_action_availability()


def _active_workflow_id(cube_view: object) -> object:
    """Return the cube view's active workflow id when available."""

    workflow_session_service = getattr(cube_view, "workflow_session_service", None)
    return getattr(workflow_session_service, "active_workflow_id", None)


def _reconcile_active_workflow_after_loaded_cube_refresh(
    workflow_workspace: object,
) -> None:
    """Run fallback active-workflow reconciliation when incremental refresh is absent."""

    reconcile = getattr(
        workflow_workspace,
        "reconcile_active_workflow_after_structural_mutation",
        None,
    )
    if callable(reconcile):
        reconcile()


def _select_loaded_cube_stack_tab(
    cube_view: object,
    active_stack: object,
    cube_alias: str,
) -> None:
    """Select a loaded cube tab when it is not already current."""

    current_tab = getattr(active_stack, "currentTab", lambda: None)()
    current_route_key = (
        current_tab.routeKey()
        if current_tab is not None and hasattr(current_tab, "routeKey")
        else None
    )
    if current_route_key == cube_alias:
        return
    select_cube = getattr(active_stack, "select_cube", None)
    if callable(select_cube):
        select_cube(cube_alias, animated=True)
        return
    get_active_workflow = getattr(cube_view, "get_active_workflow", None)
    if not callable(get_active_workflow):
        return
    set_current_index = getattr(active_stack, "setCurrentIndex", None)
    if not callable(set_current_index):
        return
    workflow = get_active_workflow()
    try:
        set_current_index(workflow.stack_order.index(cube_alias))
    except (AttributeError, ValueError):
        return


def _reveal_loaded_cube_in_editor(
    active_panel: object,
    *,
    workflow_id: str,
    cube_alias: str,
) -> None:
    """Reveal a loaded cube in the active editor surface."""

    reveal_loaded_cube = getattr(active_panel, "reveal_loaded_cube", None)
    if callable(reveal_loaded_cube):
        reveal_loaded_cube(cube_alias)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="loaded_cube_activate_reveal_called",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reveal_method="reveal_loaded_cube",
        )
        return
    reveal_new_cube = getattr(active_panel, "reveal_new_cube", None)
    if callable(reveal_new_cube):
        reveal_new_cube(cube_alias)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="loaded_cube_activate_reveal_called",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reveal_method="reveal_new_cube",
        )


def cube_stack_tab_index(cube_stack: object, cube_alias: str) -> int | None:
    """Return the current tab index for one cube alias route key."""

    count = getattr(cube_stack, "count", None)
    tab_item = getattr(cube_stack, "tabItem", None)
    if not callable(count) or not callable(tab_item):
        return None
    try:
        tab_count = int(count())
    except (RuntimeError, TypeError, ValueError):
        return None
    for index in range(tab_count):
        try:
            item = tab_item(index)
        except (IndexError, RuntimeError, TypeError, ValueError):
            continue
        route_key = getattr(item, "routeKey", None)
        if callable(route_key) and route_key() == cube_alias:
            return index
    return None


__all__ = [
    "activate_loaded_cube_surface",
    "build_cube_load_ui_callbacks_for_view",
    "cube_stack_tab_index",
    "mark_loaded_cube_surface_stale",
    "refresh_active_cube_stack_tab_for_view",
    "refresh_incremental_loaded_cube_surface",
    "refresh_loaded_cube_surface_for_view",
    "refresh_loaded_cube_surface_for_view_async",
    "refresh_workflow_after_cube_load_for_view",
    "refresh_workflow_after_cube_load_for_view_async",
    "schedule_deferred_incremental_override_presentation_rebuild",
]
