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

"""Project loaded cubes incrementally and refresh dependent shell controls."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter

from substitute.shared.logging.logger import get_logger, log_debug, log_info, log_timing

_LOGGER = get_logger("presentation.shell.loaded_cube_incremental_refresh")


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
            getattr(workflow_session_service, "active_workflow_id", "")
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
        mounted_control_count = getattr(active_manager, "mounted_control_count", None)
        log_timing(
            _LOGGER,
            "Rebuilt incremental override presentation",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            override_control_count=(
                int(mounted_control_count()) if callable(mounted_control_count) else 0
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
            workflow_cube_aliases=(
                list(cubes or {}) if isinstance(cubes, Mapping) else []
            ),
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
        _refresh_override_manager(
            workflow_workspace_view=workflow_workspace_view,
            workflow_id=workflow_id,
            schedule_deferred_rebuild=schedule_deferred_rebuild,
        )
        _refresh_dependent_controls(workflow_workspace_view)
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
        motion_requested=True,
    )
    return True


def _refresh_override_manager(
    *,
    workflow_workspace_view: object,
    workflow_id: str,
    schedule_deferred_rebuild: Callable[[Callable[[], None]], None],
) -> None:
    """Refresh override state after one loaded-cube editor insertion."""

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


def _refresh_dependent_controls(workflow_workspace_view: object) -> None:
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


__all__ = [
    "refresh_incremental_loaded_cube_surface",
    "schedule_deferred_incremental_override_presentation_rebuild",
]
