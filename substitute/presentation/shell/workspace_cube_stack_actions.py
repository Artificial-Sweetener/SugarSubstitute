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

"""Coordinate cube-card commands for the active workflow stack."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QTimer

from substitute.application.workflows import CubeDuplicationService
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.cube_removal_projection import (
    clear_cube_runtime_issues,
    remove_editor_cube_section,
)
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeStackProtocol as PresentationCubeStackProtocol,
)
from substitute.presentation.shell.cube_surface_projection_coordinator import (
    CubeSurfaceProjectionCoordinator,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    CUBE_STRUCTURE_SURFACES,
    WorkflowInvalidationReason,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.shell.workspace_cube_stack_actions")


def _mark_workflow_surfaces_dirty(
    view: object,
    workflow_id: str,
    *,
    reason: WorkflowInvalidationReason,
) -> None:
    """Record cube-structure maintenance intent when the shell exposes tracking."""

    service = getattr(view, "workflow_surface_invalidation_service", None)
    mark_dirty = getattr(service, "mark_dirty", None)
    if callable(mark_dirty):
        mark_dirty(workflow_id, CUBE_STRUCTURE_SURFACES, reason)


class CubeStackTabItemProtocol(Protocol):
    """Describe mutable cube-card route and label operations."""

    def routeKey(self) -> str:
        """Return the cube route key."""

    def setRouteKey(self, key: str) -> None:
        """Replace the cube route key."""

    def setText(self, text: str) -> None:
        """Replace the rendered cube label."""

    def setToolTip(self, text: str) -> None:
        """Replace the rendered cube tooltip."""


class CubeStackProtocol(Protocol):
    """Describe cube-stack behavior used by card commands."""

    itemMap: dict[str, CubeStackTabItemProtocol]

    def insertTab(
        self,
        index: int,
        *,
        routeKey: str,
        text: str,
        icon: object | None = None,
    ) -> object:
        """Insert one cube card."""

    def setTabIcon(self, index: int, icon: object) -> None:
        """Set one cube-card icon."""

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Set complete cube-card text presentation."""

    def setTabIssueSeverity(self, route_key: str, severity: str | None) -> None:
        """Set issue severity for one cube card."""

    def count(self) -> int:
        """Return the number of cube cards."""

    def tabItem(self, index: int) -> CubeStackTabItemProtocol:
        """Return the cube card at an index."""

    def setCurrentIndex(self, index: int) -> None:
        """Select a cube card."""

    def removeTab(self, index: int) -> None:
        """Remove a cube card."""

    def begin_alias_editing(self, route_key: str) -> bool:
        """Begin alias editing for one route key."""

    def isCompact(self) -> bool:
        """Return whether the stack is compact."""

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Set bypass presentation for one cube card."""


class EditorPanelProtocol(Protocol):
    """Describe editor-panel operations used by cube-card commands."""

    def scroll_to_cube(self, route_key: str, animated: bool = False) -> None:
        """Scroll to one cube section."""

    def rename_cube(self, old_key: str, new_key: str) -> None:
        """Rename one cube section."""

    def refresh_cube_header(self, alias: str) -> None:
        """Refresh one cube section header."""


class CubeRenameResolutionProtocol(Protocol):
    """Describe a centrally resolved cube alias."""

    resolved_alias: str


class CubeStackServiceProtocol(Protocol):
    """Describe workflow mutations needed by cube-card commands."""

    def apply_reordered_aliases(self, workflow: object, new_order: list[str]) -> None:
        """Synchronize reordered aliases into workflow state."""

    def apply_cube_removal(self, workflow: object, alias_name: str) -> None:
        """Remove one cube from workflow state."""

    def apply_cube_rename(
        self,
        workflow: object,
        old_alias: str,
        requested_alias: str,
    ) -> CubeRenameResolutionProtocol:
        """Rename one cube in workflow state."""

    def toggle_cube_bypassed(self, workflow: object, alias_name: str) -> bool:
        """Toggle cube bypass and return its new value."""

    def toggle_cube_output_persistence(self, workflow: object, alias_name: str) -> bool:
        """Toggle cube output persistence and return its new value."""


class CubeStackExpansionLeaseProtocol(Protocol):
    """Describe one cancellable temporary cube-stack expansion."""

    def release(self) -> None:
        """Release the temporary expansion exactly once."""


class CubeStackPresentationControllerProtocol(Protocol):
    """Describe temporary expansion used during inline alias editing."""

    def acquire_expansion(
        self,
        *,
        on_expanded: Callable[[], None] | None = None,
    ) -> CubeStackExpansionLeaseProtocol:
        """Expand temporarily and notify when the endpoint is ready."""


class ActiveWorkflowSurfaceRefresherProtocol(Protocol):
    """Describe structural active-workflow surface reconciliation."""

    def refresh_active_workflow_surface(
        self,
        *,
        force_refresh: bool = False,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Refresh active workflow surfaces after a cube mutation."""


class WorkspaceCubeStackActionView(Protocol):
    """Describe the shell surface consumed by cube-card commands."""

    cube_stack_service: CubeStackServiceProtocol
    workflow_session_service: object
    active_cube_stack: CubeStackProtocol | None
    active_editor_panel: EditorPanelProtocol | None
    cube_stack_presentation_controller: CubeStackPresentationControllerProtocol
    active_workflow_surface_refresher: ActiveWorkflowSurfaceRefresherProtocol

    def get_active_workflow(self) -> WorkflowState:
        """Return the active workflow state."""


@dataclass(slots=True)
class CubeRenameEditSession:
    """Track one alias edit and its cancellable temporary expansion."""

    route_key: str
    session_id: int
    expansion_lease: CubeStackExpansionLeaseProtocol | None = None


class WorkspaceCubeStackActions:
    """Own active cube-card rename, bypass, ordering, removal, and navigation."""

    def __init__(
        self,
        view: WorkspaceCubeStackActionView,
        *,
        duplication_service: CubeDuplicationService,
        stack_presenter: CubeStackPresenter,
        surface_projector: CubeSurfaceProjectionCoordinator,
    ) -> None:
        """Store the shell view used by cube-card commands."""

        self._view = view
        self._duplication_service = duplication_service
        self._stack_presenter = stack_presenter
        self._surface_projector = surface_projector
        self._cube_rename_edit_session: CubeRenameEditSession | None = None
        self._cube_rename_edit_session_id = 0

    def highlight_tab_for_cube(self, cube_alias: str) -> None:
        """Highlight the cube card matching the selected editor cube."""

        active_stack = self._view.active_cube_stack
        if active_stack is None:
            return
        try:
            workflow = self._view.get_active_workflow()
            select_cube = getattr(active_stack, "select_cube", None)
            if callable(select_cube):
                select_cube(cube_alias, animated=True)
                return
            active_stack.setCurrentIndex(workflow.stack_order.index(cube_alias))
        except ValueError:
            log_warning(
                _LOGGER, "Cube alias not found in stack order", cube_alias=cube_alias
            )

    def on_cube_rename_edit_requested(self, route_key: str) -> None:
        """Open alias editing, temporarily expanding a compact stack."""

        active_stack = self._view.active_cube_stack
        if active_stack is None:
            return
        session = self._start_cube_rename_edit_session(route_key)

        def begin_editing() -> None:
            """Begin editing after temporary expansion completes."""

            self._begin_cube_alias_editing_for_session(session)

        lease = self._view.cube_stack_presentation_controller.acquire_expansion(
            on_expanded=begin_editing,
        )
        session.expansion_lease = lease
        if self._cube_rename_edit_session is not session:
            lease.release()

    def on_cube_rename_edit_finished(self, route_key: str) -> None:
        """Restore compact mode after a coordinated alias-edit session."""

        session = self._cube_rename_edit_session
        if session is None or session.route_key != route_key:
            return
        self._cube_rename_edit_session = None
        if session.expansion_lease is not None:
            session.expansion_lease.release()

    def on_cube_rename_requested(
        self,
        old_key: str,
        requested_key: str,
        *,
        timer: type[QTimer] = QTimer,
    ) -> None:
        """Resolve a cube rename and synchronize shell and editor state."""

        active_stack = self._view.active_cube_stack
        active_panel = self._view.active_editor_panel
        if active_stack is None or active_panel is None:
            return
        workflow = self._view.get_active_workflow()
        resolution = self._view.cube_stack_service.apply_cube_rename(
            workflow,
            old_key,
            requested_key,
        )
        resolved_alias = resolution.resolved_alias
        self._apply_resolved_stack_alias(active_stack, old_key, resolved_alias)
        active_panel.rename_cube(old_key, resolved_alias)
        timer.singleShot(
            0,
            lambda: active_panel.scroll_to_cube(resolved_alias, animated=True),
        )

    def on_cube_bypass_toggle_requested(self, alias_name: str) -> None:
        """Toggle cube bypass state and refresh active shell surfaces."""

        view = self._view
        active_stack = view.active_cube_stack
        workflow = view.get_active_workflow()
        if active_stack is None or alias_name not in workflow.cubes:
            return
        bypassed = view.cube_stack_service.toggle_cube_bypassed(workflow, alias_name)
        tab_index = _stack_index_for_route_key(active_stack, alias_name)
        if tab_index is not None:
            active_stack.setTabBypassed(tab_index, bypassed)
        active_panel = view.active_editor_panel
        refresh_header = getattr(active_panel, "refresh_cube_header", None)
        if callable(refresh_header):
            refresh_header(alias_name)
        workflow_id = _active_workflow_id(view)
        _mark_workflow_surfaces_dirty(
            view,
            workflow_id,
            reason=WorkflowInvalidationReason.CUBE_BYPASS_CHANGED,
        )
        view.active_workflow_surface_refresher.refresh_active_workflow_surface()

    def on_cube_output_persistence_toggle_requested(self, alias_name: str) -> None:
        """Toggle whether one workflow cube instance writes output files."""

        view = self._view
        active_stack = view.active_cube_stack
        workflow = view.get_active_workflow()
        if active_stack is None or alias_name not in workflow.cubes:
            return
        enabled = view.cube_stack_service.toggle_cube_output_persistence(
            workflow, alias_name
        )
        tab_index = _stack_index_for_route_key(active_stack, alias_name)
        if tab_index is not None:
            setter = getattr(active_stack, "setTabOutputPersistenceEnabled", None)
            if callable(setter):
                setter(tab_index, enabled)
        _mark_workflow_surfaces_dirty(
            view,
            _active_workflow_id(view),
            reason=WorkflowInvalidationReason.CUBE_OUTPUT_PERSISTENCE_CHANGED,
        )

    def on_cube_duplicate_requested(self, source_alias: str) -> None:
        """Duplicate one cube and project the appended copy across active surfaces."""

        view = self._view
        active_stack = view.active_cube_stack
        if active_stack is None:
            return
        workflow = view.get_active_workflow()
        result = self._duplication_service.duplicate_cube(workflow, source_alias)
        if result is None:
            return
        workflow_id = _active_workflow_id(view)
        self._stack_presenter.append_cube(
            cast(PresentationCubeStackProtocol, active_stack),
            workflow_id=workflow_id,
            cube_alias=result.duplicate_alias,
            cube_state=result.duplicate_state,
            issue_state=getattr(view, "workflow_issue_state", None),
            select=True,
        )
        _mark_workflow_surfaces_dirty(
            view,
            workflow_id,
            reason=WorkflowInvalidationReason.CUBE_DUPLICATED,
        )
        self._surface_projector.project_added_cube(
            workflow_id,
            result.duplicate_alias,
        )

    def on_cube_move_finished(self) -> None:
        """Persist cube drag order from the active stack into workflow state."""

        view = self._view
        active_stack = view.active_cube_stack
        if active_stack is None or view.active_editor_panel is None:
            return
        new_order = [
            active_stack.tabItem(index).routeKey()
            for index in range(active_stack.count())
        ]
        view.cube_stack_service.apply_reordered_aliases(
            view.get_active_workflow(),
            new_order,
        )
        workflow_id = _active_workflow_id(view)
        _mark_workflow_surfaces_dirty(
            view,
            workflow_id,
            reason=WorkflowInvalidationReason.CUBE_REORDERED,
        )
        view.active_workflow_surface_refresher.refresh_active_workflow_surface()

    def on_cube_close_requested(self, index: int) -> None:
        """Remove one cube from the active workflow."""

        view = self._view
        active_stack = view.active_cube_stack
        if active_stack is None:
            return
        alias_name = active_stack.tabItem(index).routeKey()
        workflow = view.get_active_workflow()
        view.cube_stack_service.apply_cube_removal(workflow, alias_name)
        workflow_id = _active_workflow_id(view)
        clear_cube_runtime_issues(view, workflow_id, alias_name)
        remove_editor_cube_section(view, alias_name)
        active_stack.removeTab(index)
        _mark_workflow_surfaces_dirty(
            view,
            workflow_id,
            reason=WorkflowInvalidationReason.CUBE_REMOVED,
        )
        view.active_workflow_surface_refresher.refresh_active_workflow_surface()

    def on_tab_mouse_released(self, index: int) -> None:
        """Scroll the editor to the cube selected from the stack."""

        active_stack = self._view.active_cube_stack
        active_panel = self._view.active_editor_panel
        if active_stack is None or active_panel is None or index < 0:
            return
        active_panel.scroll_to_cube(
            active_stack.tabItem(index).routeKey(),
            animated=True,
        )

    @staticmethod
    def _apply_resolved_stack_alias(
        active_stack: CubeStackProtocol,
        old_alias: str,
        resolved_alias: str,
    ) -> None:
        """Synchronize one resolved alias into the active stack widget."""

        tab_item = active_stack.itemMap.get(old_alias)
        if tab_item is None:
            return
        tab_item.setText(resolved_alias)
        set_fluent_tooltip_text(tab_item, resolved_alias)
        tab_item.setRouteKey(resolved_alias)
        active_stack.itemMap.pop(old_alias, None)
        active_stack.itemMap[resolved_alias] = tab_item

    def _start_cube_rename_edit_session(
        self,
        route_key: str,
    ) -> CubeRenameEditSession:
        """Replace the active alias-edit session."""

        previous_session = self._cube_rename_edit_session
        if (
            previous_session is not None
            and previous_session.expansion_lease is not None
        ):
            previous_session.expansion_lease.release()
        self._cube_rename_edit_session_id += 1
        session = CubeRenameEditSession(
            route_key=route_key,
            session_id=self._cube_rename_edit_session_id,
        )
        self._cube_rename_edit_session = session
        return session

    def _begin_cube_alias_editing_for_session(
        self,
        session: CubeRenameEditSession,
    ) -> None:
        """Start alias editing for the active session after expansion."""

        if self._cube_rename_edit_session != session:
            return
        active_stack = self._view.active_cube_stack
        if active_stack is not None and active_stack.begin_alias_editing(
            session.route_key
        ):
            return
        self._cube_rename_edit_session = None
        if session.expansion_lease is not None:
            session.expansion_lease.release()


def _stack_index_for_route_key(
    active_stack: CubeStackProtocol,
    route_key: str,
) -> int | None:
    """Return the active stack index for a route key when present."""

    for index in range(active_stack.count()):
        if active_stack.tabItem(index).routeKey() == route_key:
            return index
    return None


def _active_workflow_id(view: object) -> str:
    """Return the active workflow id when session state is available."""

    session = getattr(view, "workflow_session_service", None)
    return str(getattr(session, "active_workflow_id", ""))


__all__ = ["WorkspaceCubeStackActionView", "WorkspaceCubeStackActions"]
