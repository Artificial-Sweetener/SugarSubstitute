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

"""Coordinate asynchronous cube loading and UI handoff for the active workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from inspect import signature
from time import perf_counter
from typing import Any, Callable, Protocol, cast
from uuid import uuid4

from PySide6.QtCore import QTimer

from substitute.application.execution import (
    ExecutionContext,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.cubes import (
    CubeLoadService,
    CubeStackService,
    CubeWorkflowAddService,
)
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeStackProtocol,
    CubeTabIconResolver,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_error,
    log_info,
    log_timing,
)

_LOGGER = get_logger("presentation.shell.cube_loader")
_CUBE_LOAD_PERF_PREFIX = "Cube load performance"

CubePayload = dict[str, Any]


class TabItemView(Protocol):
    """Define route-key behavior required for cube-tab updates."""

    def routeKey(self) -> str: ...

    def setRouteKey(self, key: str) -> None: ...


class CubeStackView(Protocol):
    """Describe cube-stack widget contract used by async cube loading."""

    itemMap: dict[str, TabItemView]

    def __bool__(self) -> bool: ...

    def setTabText(self, index: int, text: str) -> None: ...

    def setTabIcon(self, index: int, icon: object) -> None: ...

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None: ...

    def tabItem(self, index: int) -> TabItemView: ...

    def setCurrentIndex(self, index: int) -> None: ...

    def count(self) -> int: ...


class EditorPanelView(Protocol):
    """Describe editor panel behavior required by cube loader callbacks."""

    def __bool__(self) -> bool: ...

    def scroll_to_cube(self, alias: str, animated: bool = True) -> None: ...

    def reveal_new_cube(self, route_key: str) -> None: ...


class WorkflowSessionState(Protocol):
    """Define workflow-session state consumed by async load flow."""

    active_workflow_id: str
    workflows: dict[str, Any]


class CubeIconFactoryProtocol(Protocol):
    """Resolve cube icon descriptors into presentation-compatible icon payloads."""

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Return a Qt-compatible icon payload for one loaded cube."""


@dataclass(frozen=True)
class CubeLoadExecutionRoute:
    """Carry the submitter and cleanup hook for one cube-load request."""

    submitter: TaskSubmitter
    close: Callable[[], None]


class CubeLoadExecutionRouteFactory(Protocol):
    """Create execution routes for cube-load requests."""

    def __call__(self, *, cube_load_trace_id: str) -> CubeLoadExecutionRoute:
        """Return the execution route for one cube-load request."""


@dataclass(frozen=True)
class CubeLoadPresentationIntent:
    """Describe how a loaded cube should be presented after editor insertion."""

    select_after_load: bool
    scroll_after_load: bool

    @classmethod
    def from_reveal_after_load(
        cls, reveal_after_load: bool
    ) -> "CubeLoadPresentationIntent":
        """Translate the legacy reveal flag into explicit presentation intent."""

        return cls(
            select_after_load=reveal_after_load,
            scroll_after_load=reveal_after_load,
        )


@dataclass(frozen=True)
class CubeLoadUiCallbacks:
    """Bundle only the collaborators load_cube_async needs from the shell layer."""

    workflow_session_service: WorkflowSessionState
    cube_stacks: Mapping[str, CubeStackView]
    editor_panels: Mapping[str, EditorPanelView]
    cube_load_service: CubeLoadService
    cube_stack_service: CubeStackService
    materialize_loaded_cube_input_canvas: Callable[[str, str], None]
    refresh_workflow_after_cube_load: Callable[[str, str], None]
    prepare_node_behavior_runtime: Callable[[Any, str], NodeBehaviorRuntimeState]
    cube_icon_factory: CubeIconFactoryProtocol
    cube_load_execution_route_factory: CubeLoadExecutionRouteFactory
    refresh_loaded_cube_surface: Callable[..., bool] | None = None
    activate_loaded_cube: Callable[[str, str], None] | None = None
    refresh_workflow_after_cube_load_async: (
        Callable[[str, str, Callable[[], None]], None] | None
    ) = None
    refresh_loaded_cube_surface_async: Callable[..., None] | None = None


@dataclass(frozen=True)
class _CubeDefinitionLoadResult:
    """Carry a cube-definition load result to the GUI thread."""

    loaded_cube: Any | None
    error: BaseException | None
    task_started_at: float = 0.0
    task_finished_at: float = 0.0
    cube_load_trace_id: str = ""


@dataclass(frozen=True)
class _CubeRuntimeBuildResult:
    """Carry prepared cube runtime state to the GUI thread."""

    loaded_runtime: Any | None
    error: BaseException | None
    task_started_at: float = 0.0
    task_finished_at: float = 0.0
    cube_load_trace_id: str = ""


def _create_cube_load_execution_route(
    callbacks: CubeLoadUiCallbacks,
    cube_load_trace_id: str,
) -> CubeLoadExecutionRoute:
    """Return the execution route for one cube-load request."""

    return callbacks.cube_load_execution_route_factory(
        cube_load_trace_id=cube_load_trace_id,
    )


def _run_cube_definition_load(
    *,
    callbacks: CubeLoadUiCallbacks,
    cube_id: str,
    cube_version: str | None,
    cube_load_trace_id: str,
    queued_at: float,
) -> _CubeDefinitionLoadResult:
    """Load one cube definition as execution-layer task work."""

    task_started_at = perf_counter()
    log_timing(
        _LOGGER,
        "Started cube definition load task after queue wait",
        started_at=queued_at,
        cube_load_trace_id=cube_load_trace_id,
        cube_id=cube_id,
        level="debug",
    )
    try:
        loaded_cube = _load_cube_definition_with_trace(
            callbacks.cube_load_service,
            cube_id,
            cube_version=cube_version,
            cube_load_trace_id=cube_load_trace_id,
        )
        result = _CubeDefinitionLoadResult(
            loaded_cube=loaded_cube,
            error=None,
            task_started_at=task_started_at,
            task_finished_at=perf_counter(),
            cube_load_trace_id=cube_load_trace_id,
        )
    except Exception as exc:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="definition_task_exception",
            cube_load_trace_id=cube_load_trace_id,
            cube_id=cube_id,
            error_type=type(exc).__name__,
            error=repr(exc),
        )
        result = _CubeDefinitionLoadResult(
            loaded_cube=None,
            error=exc,
            task_started_at=task_started_at,
            task_finished_at=perf_counter(),
            cube_load_trace_id=cube_load_trace_id,
        )
    log_timing(
        _LOGGER,
        "Completed cube definition load task execution",
        started_at=task_started_at,
        cube_load_trace_id=cube_load_trace_id,
        cube_id=cube_id,
        succeeded=result.error is None,
        level="debug",
    )
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="definition_task_post_result",
        cube_load_trace_id=cube_load_trace_id,
        cube_id=cube_id,
        succeeded=result.error is None,
        loaded_cube_id=getattr(result.loaded_cube, "cube_id", None),
        node_count=_safe_loaded_cube_node_count(result.loaded_cube),
        error_type=type(result.error).__name__ if result.error is not None else "",
    )
    return result


def _run_cube_runtime_build(
    *,
    callbacks: CubeLoadUiCallbacks,
    cube_id: str,
    alias_name: str,
    buffer_patch: CubePayload | None,
    loaded_cube: Any,
    cube_load_trace_id: str,
    queued_at: float,
) -> _CubeRuntimeBuildResult:
    """Build loaded cube runtime state as execution-layer task work."""

    task_started_at = perf_counter()
    log_timing(
        _LOGGER,
        "Started cube runtime build task after queue wait",
        started_at=queued_at,
        cube_load_trace_id=cube_load_trace_id,
        cube_id=cube_id,
        cube_alias=alias_name,
        level="debug",
    )
    try:
        phase_started_at = perf_counter()
        runtime_state = callbacks.prepare_node_behavior_runtime(
            loaded_cube,
            alias_name,
        )
        log_timing(
            _LOGGER,
            "Prepared cube node behavior runtime state",
            started_at=phase_started_at,
            cube_load_trace_id=cube_load_trace_id,
            cube_id=cube_id,
            cube_alias=alias_name,
            level="debug",
        )
        loaded_runtime = _build_loaded_cube_runtime_with_trace(
            callbacks.cube_load_service,
            cube_id,
            alias_name,
            buffer_patch=buffer_patch,
            runtime_state=runtime_state,
            loaded_cube_definition=loaded_cube,
            cube_load_trace_id=cube_load_trace_id,
        )
        result = _CubeRuntimeBuildResult(
            loaded_runtime=loaded_runtime,
            error=None,
            task_started_at=task_started_at,
            task_finished_at=perf_counter(),
            cube_load_trace_id=cube_load_trace_id,
        )
    except Exception as exc:
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="runtime_task_exception",
            cube_load_trace_id=cube_load_trace_id,
            cube_id=cube_id,
            cube_alias=alias_name,
            error_type=type(exc).__name__,
            error=repr(exc),
        )
        result = _CubeRuntimeBuildResult(
            loaded_runtime=None,
            error=exc,
            task_started_at=task_started_at,
            task_finished_at=perf_counter(),
            cube_load_trace_id=cube_load_trace_id,
        )
    log_timing(
        _LOGGER,
        "Completed cube runtime build task execution",
        started_at=task_started_at,
        cube_load_trace_id=cube_load_trace_id,
        cube_id=cube_id,
        cube_alias=alias_name,
        succeeded=result.error is None,
        level="debug",
    )
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="runtime_task_post_result",
        cube_load_trace_id=cube_load_trace_id,
        cube_id=cube_id,
        cube_alias=alias_name,
        succeeded=result.error is None,
        loaded_runtime_cube_id=getattr(result.loaded_runtime, "cube_id", None),
        loaded_runtime_alias=getattr(
            getattr(result.loaded_runtime, "cube_state", None),
            "alias",
            None,
        ),
        error_type=type(result.error).__name__ if result.error is not None else "",
    )
    return result


def _cube_definition_result_from_outcome(
    outcome: TaskOutcome[_CubeDefinitionLoadResult],
) -> _CubeDefinitionLoadResult:
    """Convert execution outcome into the legacy cube definition result."""

    if outcome.result is not None:
        return outcome.result
    error = outcome.error
    if error is None and outcome.cancelled:
        error = RuntimeError(outcome.cancellation_reason or "cancelled")
    if error is None:
        error = RuntimeError("Cube definition load produced no outcome.")
    return _CubeDefinitionLoadResult(
        loaded_cube=None,
        error=error,
        cube_load_trace_id=str(outcome.context.field_value("trace_id") or ""),
    )


def _cube_runtime_result_from_outcome(
    outcome: TaskOutcome[_CubeRuntimeBuildResult],
) -> _CubeRuntimeBuildResult:
    """Convert execution outcome into the legacy cube runtime result."""

    if outcome.result is not None:
        return outcome.result
    error = outcome.error
    if error is None and outcome.cancelled:
        error = RuntimeError(outcome.cancellation_reason or "cancelled")
    if error is None:
        error = RuntimeError("Cube runtime build produced no outcome.")
    return _CubeRuntimeBuildResult(
        loaded_runtime=None,
        error=error,
        cube_load_trace_id=str(outcome.context.field_value("trace_id") or ""),
    )


def load_cube_async(
    callbacks: CubeLoadUiCallbacks,
    cube_id: str,
    alias_name: str,
    placeholder_index: int,
    buffer_patch: CubePayload | None = None,
    *,
    reveal_after_load: bool = True,
    presentation_intent: CubeLoadPresentationIntent | None = None,
    on_load_finished: Callable[[str | None], None] | None = None,
    cube_load_trace_id: str | None = None,
) -> None:
    """Load cube data asynchronously and update captured workflow UI state."""

    total_started_at = perf_counter()
    resolved_trace_id = cube_load_trace_id or uuid4().hex
    intent = presentation_intent or CubeLoadPresentationIntent.from_reveal_after_load(
        reveal_after_load
    )
    requested_cube_version = _version_pin_from_buffer_patch(buffer_patch)
    target_workflow_id = callbacks.workflow_session_service.active_workflow_id
    target_cube_stack = callbacks.cube_stacks.get(target_workflow_id)
    target_editor_panel = callbacks.editor_panels.get(target_workflow_id)
    execution_route = _create_cube_load_execution_route(callbacks, resolved_trace_id)
    execution_scope = TaskScope(
        submitter=execution_route.submitter,
        scope_id=f"cube_load_{resolved_trace_id}",
    )
    placeholder_route_key = _placeholder_route_key(
        target_cube_stack,
        placeholder_index,
        alias_name,
    )
    completion_reported = False
    log_debug(
        _LOGGER,
        "Cube load detail",
        event="load_request_start",
        workflow_id=target_workflow_id,
        cube_id=cube_id,
        requested_alias=alias_name,
        requested_cube_version=requested_cube_version or "",
        cube_load_trace_id=resolved_trace_id,
        placeholder_index=placeholder_index,
        placeholder_route_key=placeholder_route_key,
        stack_route_keys=_stack_route_keys(target_cube_stack),
        editor_panel_present=target_editor_panel is not None,
        workflow_ids=list(callbacks.workflow_session_service.workflows),
        reveal_after_load=reveal_after_load,
        select_after_load=intent.select_after_load,
        scroll_after_load=intent.scroll_after_load,
        has_buffer_patch=buffer_patch is not None,
    )
    log_info(
        _LOGGER,
        "Started cube load request",
        workflow_id=target_workflow_id,
        cube_id=cube_id,
        requested_alias=alias_name,
        requested_cube_version=requested_cube_version or "",
        cube_load_trace_id=resolved_trace_id,
        placeholder_index=placeholder_index,
        placeholder_route_key=placeholder_route_key,
        has_cube_stack=target_cube_stack is not None,
        has_editor_panel=target_editor_panel is not None,
        reveal_after_load=reveal_after_load,
        select_after_load=intent.select_after_load,
        scroll_after_load=intent.scroll_after_load,
        has_buffer_patch=buffer_patch is not None,
    )

    def report_load_finished(resolved_alias: str | None) -> None:
        """Notify batch orchestration once per cube load attempt."""

        nonlocal completion_reported
        log_info(
            _LOGGER,
            f"{_CUBE_LOAD_PERF_PREFIX} report_load_finished entered",
            workflow_id=target_workflow_id,
            cube_id=cube_id,
            cube_alias=resolved_alias or alias_name,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            completion_reported=completion_reported,
            has_on_load_finished=on_load_finished is not None,
        )
        if completion_reported:
            return
        completion_reported = True
        execution_scope.close(reason="cube_load_finished")
        execution_route.close()
        log_timing(
            _LOGGER,
            "Completed cube load request",
            started_at=total_started_at,
            workflow_id=target_workflow_id,
            cube_id=cube_id,
            cube_alias=resolved_alias or alias_name,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            succeeded=resolved_alias is not None,
            level="debug",
        )
        if on_load_finished is not None:
            on_load_finished(resolved_alias)
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="load_finished_reported",
            workflow_id=target_workflow_id,
            cube_id=cube_id,
            requested_alias=alias_name,
            resolved_alias=resolved_alias,
            cube_load_trace_id=resolved_trace_id,
            completion_reported=completion_reported,
        )

    def finish_loaded_runtime(
        result: _CubeRuntimeBuildResult,
        *,
        load_started_at: float,
    ) -> None:
        """Commit prepared runtime state to workflow and editor UI."""

        if result.task_finished_at > 0:
            log_timing(
                _LOGGER,
                "Delivered cube runtime task result to GUI thread",
                started_at=result.task_finished_at,
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                cube_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                succeeded=result.error is None,
                level="debug",
            )
        loaded_runtime = result.loaded_runtime
        loaded_cube_id = cube_id
        cube_def: CubePayload | None = None
        if result.error is not None:
            log_error(
                _LOGGER,
                "Failed to load cube",
                cube_id=cube_id,
                cube_load_trace_id=resolved_trace_id,
                error=result.error,
            )
        elif loaded_runtime is not None:
            loaded_cube_id = loaded_runtime.cube_id
            cube_def = loaded_runtime.cube_definition

        active_cube_stack = target_cube_stack
        active_editor_panel = target_editor_panel
        if not active_cube_stack or not active_editor_panel:
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="runtime_finish_missing_ui",
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                active_cube_stack_present=active_cube_stack is not None,
                active_editor_panel_present=active_editor_panel is not None,
            )
            report_load_finished(None)
            return
        current_placeholder_index = _find_tab_index(
            active_cube_stack,
            placeholder_route_key,
        )
        if current_placeholder_index is None:
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="runtime_finish_missing_placeholder",
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                placeholder_route_key=placeholder_route_key,
                stack_route_keys=_stack_route_keys(active_cube_stack),
            )
            log_error(
                _LOGGER,
                "Skipped cube load completion because placeholder tab was missing",
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                cube_alias=alias_name,
                placeholder_route_key=placeholder_route_key,
            )
            report_load_finished(None)
            return

        if cube_def is None or loaded_runtime is None:
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="runtime_finish_failed_payload",
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                error_type=type(result.error).__name__ if result.error else "",
                stack_route_keys=_stack_route_keys(active_cube_stack),
            )
            active_cube_stack.setTabPresentation(
                current_placeholder_index,
                primary_text=f"{alias_name} (Failed)",
                secondary_text="",
                tooltip_text=f"{alias_name} (Failed)",
            )
            report_load_finished(None)
            return

        workflow = callbacks.workflow_session_service.workflows.get(target_workflow_id)
        if workflow is None:
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="runtime_finish_missing_workflow",
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                workflow_ids=list(callbacks.workflow_session_service.workflows),
            )
            report_load_finished(None)
            return
        phase_started_at = perf_counter()
        add_result = CubeWorkflowAddService(
            callbacks.cube_stack_service
        ).add_loaded_cube(
            workflow,
            cube_id=loaded_cube_id,
            requested_alias=alias_name,
            cube_state=loaded_runtime.cube_state,
        )
        resolved_alias = add_result.alias
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="workflow_state_mutated",
            workflow_id=target_workflow_id,
            cube_id=loaded_cube_id,
            requested_alias=alias_name,
            resolved_alias=resolved_alias,
            cube_load_trace_id=resolved_trace_id,
            workflow_stack_order=list(getattr(workflow, "stack_order", []) or []),
            workflow_cube_aliases=list(getattr(workflow, "cubes", {}) or {}),
        )
        log_timing(
            _LOGGER,
            "Applied loaded cube to workflow state",
            started_at=phase_started_at,
            workflow_id=target_workflow_id,
            cube_id=loaded_cube_id,
            cube_alias=resolved_alias,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            stack_order_count=len(getattr(workflow, "stack_order", []) or []),
            level="debug",
        )

        phase_started_at = perf_counter()
        presentation_result = CubeStackPresenter(
            icon_resolver=CubeTabIconResolver(
                cube_icon_factory=callbacks.cube_icon_factory,
            ),
        ).promote_placeholder(
            cast(CubeStackProtocol, active_cube_stack),
            current_placeholder_index,
            workflow_id=target_workflow_id,
            cube_alias=resolved_alias,
            cube_state=loaded_runtime.cube_state,
            select=True,
        )
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="placeholder_promoted",
            workflow_id=target_workflow_id,
            cube_id=loaded_cube_id,
            requested_alias=alias_name,
            resolved_alias=resolved_alias,
            cube_load_trace_id=resolved_trace_id,
            current_placeholder_index=current_placeholder_index,
            stack_route_keys=_stack_route_keys(active_cube_stack),
            used_fallback_icon=presentation_result.used_fallback_icon,
            warning_count=len(presentation_result.warnings),
        )
        log_timing(
            _LOGGER,
            "Promoted loaded cube placeholder tab",
            started_at=phase_started_at,
            workflow_id=target_workflow_id,
            cube_id=loaded_cube_id,
            cube_alias=resolved_alias,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            tab_index=current_placeholder_index,
            used_fallback_icon=presentation_result.used_fallback_icon,
            warning_count=len(presentation_result.warnings),
            level="debug",
        )

        def finish_ui_handoff(delayed_started_at: float) -> None:
            """Finish cube-load UI handoff after scheduled commit phases complete."""

            log_info(
                _LOGGER,
                f"{_CUBE_LOAD_PERF_PREFIX} finish_ui_handoff entered",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                select_after_load=intent.select_after_load,
                scroll_after_load=intent.scroll_after_load,
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="finish_ui_handoff",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                requested_alias=alias_name,
                resolved_alias=resolved_alias,
                cube_load_trace_id=resolved_trace_id,
                select_after_load=intent.select_after_load,
                scroll_after_load=intent.scroll_after_load,
            )
            report_load_finished(resolved_alias)
            log_timing(
                _LOGGER,
                "Completed cube load UI refresh handoff",
                started_at=delayed_started_at,
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                level="debug",
            )

        def materialize_input_canvas(delayed_started_at: float) -> None:
            """Materialize input canvas data in its own GUI event-loop turn."""

            log_info(
                _LOGGER,
                f"{_CUBE_LOAD_PERF_PREFIX} materialize_input_canvas entered",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
            )
            phase_started_at = perf_counter()
            callbacks.materialize_loaded_cube_input_canvas(
                target_workflow_id,
                resolved_alias,
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="materialized_input_canvas",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                requested_alias=alias_name,
                resolved_alias=resolved_alias,
                cube_load_trace_id=resolved_trace_id,
            )
            log_timing(
                _LOGGER,
                "Materialized loaded cube input canvas",
                started_at=phase_started_at,
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                level="debug",
            )
            log_info(
                _LOGGER,
                f"{_CUBE_LOAD_PERF_PREFIX} scheduling finish_ui_handoff",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
            )
            QTimer.singleShot(0, lambda: finish_ui_handoff(delayed_started_at))

        def refresh_loaded_surface(delayed_started_at: float) -> None:
            """Refresh editor surfaces in a scheduled GUI event-loop turn."""

            log_info(
                _LOGGER,
                f"{_CUBE_LOAD_PERF_PREFIX} refresh_loaded_surface entered",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                select_after_load=intent.select_after_load,
                scroll_after_load=intent.scroll_after_load,
                has_refresh_workflow_after_cube_load_async=(
                    callbacks.refresh_workflow_after_cube_load_async is not None
                ),
                has_refresh_loaded_cube_surface_async=(
                    callbacks.refresh_loaded_cube_surface_async is not None
                ),
            )

            def schedule_materialize_input_canvas() -> None:
                """Continue the handoff after editor refresh work has completed."""

                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} scheduling materialize_input_canvas",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                )
                QTimer.singleShot(
                    0,
                    lambda: materialize_input_canvas(delayed_started_at),
                )

            def complete_refresh() -> None:
                """Log refresh completion and continue the UI handoff."""

                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} complete_refresh entered",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                )
                schedule_materialize_input_canvas()

            if (
                intent.select_after_load or intent.scroll_after_load
            ) and callbacks.refresh_workflow_after_cube_load_async:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="refresh_path_selected",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    requested_alias=alias_name,
                    resolved_alias=resolved_alias,
                    cube_load_trace_id=resolved_trace_id,
                    refresh_path="refresh_workflow_after_cube_load_async",
                )
                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} calling refresh_workflow_after_cube_load_async",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                )
                callbacks.refresh_workflow_after_cube_load_async(
                    target_workflow_id,
                    resolved_alias,
                    complete_refresh,
                )
                return
            if (
                not (intent.select_after_load or intent.scroll_after_load)
                and callbacks.refresh_loaded_cube_surface_async is not None
            ):
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="refresh_path_selected",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    requested_alias=alias_name,
                    resolved_alias=resolved_alias,
                    cube_load_trace_id=resolved_trace_id,
                    refresh_path="refresh_loaded_cube_surface_async_complete",
                )
                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} calling refresh_loaded_cube_surface_async",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                )

                def complete_silent_refresh(_refreshed: bool) -> None:
                    """Continue handoff after a successful silent editor insert."""

                    complete_refresh()

                callbacks.refresh_loaded_cube_surface_async(
                    target_workflow_id,
                    resolved_alias,
                    complete_silent_refresh,
                    wait_for_complete=True,
                )
                return
            if intent.select_after_load or intent.scroll_after_load:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="refresh_path_selected",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    requested_alias=alias_name,
                    resolved_alias=resolved_alias,
                    cube_load_trace_id=resolved_trace_id,
                    refresh_path="refresh_workflow_after_cube_load_sync",
                )
                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} calling sync refresh_workflow_after_cube_load",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                )
                phase_started_at = perf_counter()
                callbacks.refresh_workflow_after_cube_load(
                    target_workflow_id,
                    resolved_alias,
                )
                log_timing(
                    _LOGGER,
                    "Refreshed workflow after cube load synchronously",
                    started_at=phase_started_at,
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    level="debug",
                )
            else:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="refresh_path_selected",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    requested_alias=alias_name,
                    resolved_alias=resolved_alias,
                    cube_load_trace_id=resolved_trace_id,
                    refresh_path="refresh_loaded_cube_surface_sync",
                    has_refresh_loaded_cube_surface=(
                        callbacks.refresh_loaded_cube_surface is not None
                    ),
                )
                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} calling sync refresh surface",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    refresh_surface=(
                        callbacks.refresh_loaded_cube_surface
                        or callbacks.refresh_workflow_after_cube_load
                    ),
                )
                phase_started_at = perf_counter()
                if callbacks.refresh_loaded_cube_surface is not None:
                    callbacks.refresh_loaded_cube_surface(
                        target_workflow_id,
                        resolved_alias,
                    )
                else:
                    callbacks.refresh_workflow_after_cube_load(
                        target_workflow_id,
                        resolved_alias,
                    )
                log_timing(
                    _LOGGER,
                    "Refreshed loaded cube surface synchronously",
                    started_at=phase_started_at,
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    level="debug",
                )
            complete_refresh()

        def synchronize_stack_order() -> None:
            """Synchronize stack order before scheduled editor/canvas commit phases."""

            delayed_started_at = perf_counter()
            try:
                raw_order = [
                    active_cube_stack.tabItem(index).routeKey()
                    for index in range(active_cube_stack.count())
                ]
                new_order = [
                    route_key
                    for route_key in raw_order
                    if not route_key.startswith("loading:")
                ]
                log_info(
                    _LOGGER,
                    f"{_CUBE_LOAD_PERF_PREFIX} synchronize_stack_order entered",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    cube_alias=resolved_alias,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    raw_order=raw_order,
                    filtered_order=new_order,
                )
                callbacks.cube_stack_service.apply_reordered_aliases(
                    workflow,
                    new_order,
                )
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="stack_order_synchronized",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    requested_alias=alias_name,
                    resolved_alias=resolved_alias,
                    cube_load_trace_id=resolved_trace_id,
                    raw_order=raw_order,
                    filtered_order=new_order,
                    workflow_stack_order=list(
                        getattr(workflow, "stack_order", []) or []
                    ),
                    stack_route_keys=_stack_route_keys(active_cube_stack),
                )
            except Exception as exc:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="stack_order_synchronize_exception",
                    workflow_id=target_workflow_id,
                    cube_id=loaded_cube_id,
                    requested_alias=alias_name,
                    resolved_alias=resolved_alias,
                    cube_load_trace_id=resolved_trace_id,
                    error_type=type(exc).__name__,
                    error=repr(exc),
                )
                log_error(
                    _LOGGER,
                    "Failed to synchronize workflow stack order after cube load",
                    workflow_id=target_workflow_id,
                    cube_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    error=exc,
                )
            log_info(
                _LOGGER,
                f"{_CUBE_LOAD_PERF_PREFIX} scheduling refresh_loaded_surface",
                workflow_id=target_workflow_id,
                cube_id=loaded_cube_id,
                cube_alias=resolved_alias,
                requested_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
            )
            QTimer.singleShot(0, lambda: refresh_loaded_surface(delayed_started_at))

        log_timing(
            _LOGGER,
            "Completed synchronous cube load callback phase",
            started_at=load_started_at,
            workflow_id=target_workflow_id,
            cube_id=loaded_cube_id,
            cube_alias=resolved_alias,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            level="debug",
        )

        log_info(
            _LOGGER,
            f"{_CUBE_LOAD_PERF_PREFIX} scheduling synchronize_stack_order",
            workflow_id=target_workflow_id,
            cube_id=loaded_cube_id,
            cube_alias=resolved_alias,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
        )
        QTimer.singleShot(0, synchronize_stack_order)

    def finish_loaded_definition(result: _CubeDefinitionLoadResult) -> None:
        """Queue runtime preparation after definition loading."""

        load_started_at = perf_counter()
        try:
            if result.task_finished_at > 0:
                log_timing(
                    _LOGGER,
                    "Delivered cube definition task result to GUI thread",
                    started_at=result.task_finished_at,
                    workflow_id=target_workflow_id,
                    cube_id=cube_id,
                    cube_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    succeeded=result.error is None,
                    level="debug",
                )
            if result.error is not None:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="definition_result_error",
                    workflow_id=target_workflow_id,
                    cube_id=cube_id,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                    error_type=type(result.error).__name__,
                    error=repr(result.error),
                )
                raise result.error
            loaded_cube = result.loaded_cube
            if loaded_cube is None:
                log_debug(
                    _LOGGER,
                    "Cube load detail",
                    event="definition_result_missing_payload",
                    workflow_id=target_workflow_id,
                    cube_id=cube_id,
                    requested_alias=alias_name,
                    cube_load_trace_id=resolved_trace_id,
                )
                raise RuntimeError("Cube definition task returned no cube payload.")
            node_count, unique_class_count = _cube_graph_counts(loaded_cube.graph)
            log_timing(
                _LOGGER,
                "Received loaded cube definition for UI handoff",
                started_at=load_started_at,
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                cube_alias=alias_name,
                cube_load_trace_id=resolved_trace_id,
                node_count=node_count,
                unique_class_count=unique_class_count,
                level="debug",
            )
            log_debug(
                _LOGGER,
                "Cube load detail",
                event="definition_result_received",
                workflow_id=target_workflow_id,
                cube_id=cube_id,
                requested_alias=alias_name,
                loaded_cube_id=getattr(loaded_cube, "cube_id", None),
                loaded_cube_version=getattr(loaded_cube, "version", None),
                cube_load_trace_id=resolved_trace_id,
                node_count=node_count,
                unique_class_count=unique_class_count,
            )
        except Exception as exc:
            finish_loaded_runtime(
                _CubeRuntimeBuildResult(loaded_runtime=None, error=exc),
                load_started_at=load_started_at,
            )
            return

        runtime_started_at = perf_counter()
        runtime_request = TaskRequest(
            identity=TaskIdentity(
                request_id=2,
                domain="cube_load",
                parts=(("cube_id", cube_id), ("alias", alias_name)),
            ),
            context=ExecutionContext(
                operation="build_cube_runtime",
                reason="cube_load",
                lane="cube_load",
                safe_fields=(
                    ("cube_id", cube_id),
                    ("alias", alias_name),
                    ("request_id", 2),
                    ("trace_id", resolved_trace_id),
                ),
            ),
            work=lambda _token: _run_cube_runtime_build(
                callbacks=callbacks,
                cube_id=cube_id,
                alias_name=alias_name,
                buffer_patch=buffer_patch,
                loaded_cube=loaded_cube,
                cube_load_trace_id=resolved_trace_id,
                queued_at=runtime_started_at,
            ),
        )
        try:
            runtime_handle = execution_scope.submit(runtime_request)
            runtime_handle.add_done_callback(
                lambda outcome: finish_loaded_runtime(
                    _cube_runtime_result_from_outcome(outcome),
                    load_started_at=load_started_at,
                ),
                reason="cube_runtime_build_completed",
            )
        except Exception as exc:
            finish_loaded_runtime(
                _CubeRuntimeBuildResult(
                    loaded_runtime=None,
                    error=exc,
                    cube_load_trace_id=resolved_trace_id,
                ),
                load_started_at=load_started_at,
            )
            return
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="runtime_task_queued",
            workflow_id=target_workflow_id,
            cube_id=cube_id,
            requested_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            loaded_cube_id=getattr(loaded_cube, "cube_id", None),
        )
        log_timing(
            _LOGGER,
            "Queued cube runtime build task",
            started_at=runtime_started_at,
            workflow_id=target_workflow_id,
            cube_id=cube_id,
            cube_alias=alias_name,
            cube_load_trace_id=resolved_trace_id,
            level="debug",
        )

    task_started_at = perf_counter()
    definition_request = TaskRequest(
        identity=TaskIdentity(
            request_id=1,
            domain="cube_load",
            parts=(("cube_id", cube_id),),
        ),
        context=ExecutionContext(
            operation="load_cube_definition",
            reason="cube_load",
            lane="cube_load",
            safe_fields=(
                ("cube_id", cube_id),
                ("request_id", 1),
                ("trace_id", resolved_trace_id),
            ),
        ),
        work=lambda _token: _run_cube_definition_load(
            callbacks=callbacks,
            cube_id=cube_id,
            cube_version=requested_cube_version,
            cube_load_trace_id=resolved_trace_id,
            queued_at=task_started_at,
        ),
    )
    try:
        definition_handle = execution_scope.submit(definition_request)
        definition_handle.add_done_callback(
            lambda outcome: finish_loaded_definition(
                _cube_definition_result_from_outcome(outcome)
            ),
            reason="cube_definition_load_completed",
        )
    except Exception as exc:
        finish_loaded_runtime(
            _CubeRuntimeBuildResult(
                loaded_runtime=None,
                error=exc,
                cube_load_trace_id=resolved_trace_id,
            ),
            load_started_at=total_started_at,
        )
        return


def _load_cube_definition_with_trace(
    cube_load_service: CubeLoadService,
    cube_id: str,
    *,
    cube_version: str | None,
    cube_load_trace_id: str,
) -> Any:
    """Call the appropriate cube definition loader with trace metadata."""

    if cube_version is not None:
        version_loader = cube_load_service.load_cube_definition_version
        if _callable_accepts_keyword(version_loader, "cube_load_trace_id"):
            try:
                return version_loader(
                    cube_id,
                    cube_version,
                    cube_load_trace_id=cube_load_trace_id,
                )
            except TypeError as error:
                if "cube_load_trace_id" not in str(error):
                    raise
        return version_loader(cube_id, cube_version)
    loader = cube_load_service.load_cube_definition
    if _callable_accepts_keyword(loader, "cube_load_trace_id"):
        try:
            return loader(cube_id, cube_load_trace_id=cube_load_trace_id)
        except TypeError as error:
            if "cube_load_trace_id" not in str(error):
                raise
    return loader(cube_id)


def _version_pin_from_buffer_patch(buffer_patch: CubePayload | None) -> str | None:
    """Return the recipe-selected cube version from a loader patch."""

    if buffer_patch is None:
        return None
    raw_policy = buffer_patch.get("update_policy")
    if raw_policy == "follow_latest":
        return None
    raw_version = buffer_patch.get("version")
    if not isinstance(raw_version, str):
        return None
    version = raw_version.strip()
    return version or None


def _stack_route_keys(cube_stack: CubeStackView | None) -> list[str]:
    """Return current cube-stack route keys for compact debug context."""

    route_keys: list[str] = []
    if cube_stack is None:
        return route_keys
    try:
        count = cube_stack.count()
    except (AttributeError, RuntimeError, TypeError):
        return route_keys
    for index in range(count):
        try:
            route_keys.append(str(cube_stack.tabItem(index).routeKey()))
        except (AttributeError, RuntimeError, TypeError):
            route_keys.append("<unreadable>")
    return route_keys


def _safe_loaded_cube_node_count(loaded_cube: object | None) -> int:
    """Return a node count from a loaded cube payload without raising."""

    graph = getattr(loaded_cube, "graph", None)
    if not isinstance(graph, Mapping):
        return 0
    nodes = graph.get("nodes", {})
    return len(nodes) if isinstance(nodes, Mapping) else 0


def _build_loaded_cube_runtime_with_trace(
    cube_load_service: CubeLoadService,
    cube_id: str,
    alias_name: str,
    *,
    buffer_patch: CubePayload | None,
    runtime_state: object | None,
    loaded_cube_definition: Any,
    cube_load_trace_id: str,
) -> Any:
    """Call runtime build with trace metadata when the service supports it."""

    builder = cube_load_service.build_loaded_cube_runtime
    if _callable_accepts_keyword(builder, "cube_load_trace_id"):
        try:
            return builder(
                cube_id,
                alias_name,
                buffer_patch=buffer_patch,
                runtime_state=runtime_state,
                loaded_cube_definition=loaded_cube_definition,
                cube_load_trace_id=cube_load_trace_id,
            )
        except TypeError as error:
            if "cube_load_trace_id" not in str(error):
                raise
    return builder(
        cube_id,
        alias_name,
        buffer_patch=buffer_patch,
        runtime_state=runtime_state,
        loaded_cube_definition=loaded_cube_definition,
    )


def _callable_accepts_keyword(callable_object: object, keyword: str) -> bool:
    """Return whether a callable explicitly accepts one keyword argument."""

    try:
        parameters = signature(cast(Callable[..., Any], callable_object)).parameters
    except (TypeError, ValueError):
        return False
    return keyword in parameters


def _cube_graph_counts(graph: Mapping[str, Any]) -> tuple[int, int]:
    """Return node and unique class counts for cube load diagnostics."""

    nodes = graph.get("nodes")
    if not isinstance(nodes, Mapping):
        return 0, 0
    class_types = {
        str(node_data.get("class_type"))
        for node_data in nodes.values()
        if isinstance(node_data, Mapping) and node_data.get("class_type") is not None
    }
    return len(nodes), len(class_types)


def _placeholder_route_key(
    cube_stack: CubeStackView | None,
    placeholder_index: int,
    alias_name: str,
) -> str:
    """Return the stable loading route key for one pending cube tab."""

    if cube_stack is None:
        return f"loading:{alias_name}"
    try:
        return cube_stack.tabItem(placeholder_index).routeKey()
    except (IndexError, RuntimeError, AttributeError):
        return f"loading:{alias_name}"


def _find_tab_index(cube_stack: CubeStackView, route_key: str) -> int | None:
    """Return the current index for one route key in a cube stack."""

    for index in range(cube_stack.count()):
        try:
            if cube_stack.tabItem(index).routeKey() == route_key:
                return index
        except (IndexError, RuntimeError, AttributeError):
            continue
    return None


__all__ = [
    "CubeIconFactoryProtocol",
    "CubeLoadExecutionRoute",
    "CubeLoadExecutionRouteFactory",
    "CubeLoadPresentationIntent",
    "CubeLoadUiCallbacks",
    "load_cube_async",
]
