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

"""Close workflows and release their workflow-scoped presentation state."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Protocol, TypeVar

from substitute.application.workflows import WorkflowSessionService
from substitute.presentation.shell.closed_workflow_history import (
    ClosedWorkflowHistory,
)
from substitute.presentation.shell.workflow_workspace_materializer import (
    WorkflowProjectionAction,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.shell.workflow_closure_coordinator")
WidgetT = TypeVar("WidgetT", bound="LifecycleWidget")


class WorkflowTabItem(Protocol):
    """Describe the route identity exposed by a workflow tab item."""

    def routeKey(self) -> str:
        """Return the workflow route key."""


class WorkflowClosureTabBar(Protocol):
    """Describe tab operations required while closing a workflow."""

    items: list[WorkflowTabItem]

    def workflow_ids_in_order(self) -> list[str]:
        """Return route keys in rendered order."""

    def remove_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Remove one workflow tab without necessarily emitting user intent."""


class LifecycleWidget(Protocol):
    """Describe deferred Qt widget disposal."""

    def deleteLater(self) -> None:
        """Schedule widget deletion."""


class WidgetContainer(Protocol):
    """Describe removal from a stacked workflow widget container."""

    def removeWidget(self, widget: object) -> None:
        """Remove a widget from the container."""


class DisposableOverrideManager(Protocol):
    """Describe override-manager resource disposal."""

    def dispose(self) -> None:
        """Dispose manager-owned widget resources."""


class OutputProjectionStateOwner(Protocol):
    """Describe output projection cleanup after workflow closure."""

    def discard_workflow_projection_state(self, workflow_id: str) -> None:
        """Release retained navigation and grouping state."""


class WorkflowInvalidationOwner(Protocol):
    """Describe invalidation cleanup for a removed workflow."""

    def remove_workflow(self, workflow_id: str) -> None:
        """Forget pending maintenance state for a closed workflow."""


class WorkflowClosureView(Protocol):
    """Describe shell state participating in workflow closure."""

    workflow_session_service: WorkflowSessionService[object]
    workflow_tabbar: WorkflowClosureTabBar
    cube_stacks: MutableMapping[str, LifecycleWidget]
    editor_panels: MutableMapping[str, LifecycleWidget]
    override_managers: MutableMapping[str, DisposableOverrideManager | None]
    cube_stack_container: WidgetContainer
    editor_panel_container: WidgetContainer
    output_canvas_projection_coordinator: OutputProjectionStateOwner


class WorkflowClosureCoordinator:
    """Own workflow close transitions and complete scoped-resource disposal."""

    def __init__(
        self,
        view: WorkflowClosureView,
        *,
        closed_workflow_history: ClosedWorkflowHistory,
        surface_invalidation: WorkflowInvalidationOwner,
        add_workflow: Callable[[], str],
        project_workflow: WorkflowProjectionAction,
    ) -> None:
        """Store explicit owners required by the close lifecycle."""

        self._view = view
        self._closed_workflow_history = closed_workflow_history
        self._surface_invalidation = surface_invalidation
        self._add_workflow = add_workflow
        self._project_workflow = project_workflow

    def close_workflow(self, workflow_id: str) -> None:
        """Close one workflow and project the selected successor exactly once."""

        view = self._view
        unsaved_controller = getattr(view, "unsaved_work_controller", None)
        confirm_close = getattr(unsaved_controller, "confirm_workflow_close", None)
        if callable(confirm_close) and not confirm_close(workflow_id):
            return
        ordered_ids = self._workflow_ids_in_order()
        close_push_result = self._closed_workflow_history.buffer_workflow(
            workflow_id,
            ordered_ids,
        )
        transition = view.workflow_session_service.close_workflow(
            workflow_id,
            ordered_ids,
        )
        self._dispose_workflow_ui(workflow_id)
        self._surface_invalidation.remove_workflow(workflow_id)
        view.output_canvas_projection_coordinator.discard_workflow_projection_state(
            workflow_id
        )
        unsaved_work_service = getattr(view, "unsaved_work_service", None)
        remove_document_state = getattr(unsaved_work_service, "remove", None)
        if callable(remove_document_state):
            remove_document_state(workflow_id)
        workflow_progress_service = getattr(view, "workflow_progress_service", None)
        remove_workflow_progress = getattr(
            workflow_progress_service,
            "remove_workflow",
            None,
        )
        if callable(remove_workflow_progress):
            remove_workflow_progress(workflow_id)
        output_image_pipeline = getattr(view, "output_image_pipeline", None)
        remove_output_workflow = getattr(output_image_pipeline, "remove_workflow", None)
        if callable(remove_output_workflow):
            remove_output_workflow(workflow_id)
        if transition.removed_workflow is not None:
            if close_push_result is not None and close_push_result.accepted:
                self._closed_workflow_history.cleanup_evicted(
                    close_push_result.evicted_records
                )
            else:
                self._closed_workflow_history.prune_workflow_images(
                    workflow_id,
                    transition.removed_workflow,
                )
        self._remove_workflow_activity(workflow_id)
        view.workflow_tabbar.remove_workflow_tab(workflow_id, emit=False)

        if transition.next_active_workflow_id is None:
            self._add_workflow()
            return
        if transition.active_changed:
            self._project_workflow(
                transition.next_active_workflow_id,
                force_refresh=True,
            )

    def _remove_workflow_activity(self, workflow_id: str) -> None:
        """Remove unread activity for a closed workflow when supported."""

        activity_service = getattr(self._view, "workflow_activity_service", None)
        remove_workflow = getattr(activity_service, "remove_workflow", None)
        if callable(remove_workflow):
            remove_workflow(workflow_id)

    def _workflow_ids_in_order(self) -> list[str]:
        """Return workflow ids from the tab bar with fallback for test doubles."""

        tabbar = self._view.workflow_tabbar
        workflow_ids_in_order = getattr(tabbar, "workflow_ids_in_order", None)
        if callable(workflow_ids_in_order):
            return list(workflow_ids_in_order())
        return [item.routeKey() for item in tabbar.items]

    def _dispose_workflow_ui(self, workflow_id: str) -> None:
        """Dispose workflow-scoped widgets and manager resources."""

        view = self._view
        self._remove_widget(
            workflow_id,
            mapping=view.cube_stacks,
            container=view.cube_stack_container,
        )
        self._remove_widget(
            workflow_id,
            mapping=view.editor_panels,
            container=view.editor_panel_container,
        )
        manager = view.override_managers.pop(workflow_id, None)
        if manager is None:
            return
        try:
            manager.dispose()
        except (AttributeError, RuntimeError, TypeError) as error:
            log_exception(
                _LOGGER,
                "Failed to dispose override manager during workflow close",
                workflow_id=workflow_id,
                error=error,
            )

    @staticmethod
    def _remove_widget(
        workflow_id: str,
        *,
        mapping: MutableMapping[str, WidgetT],
        container: WidgetContainer,
    ) -> None:
        """Remove one workflow-scoped widget from its mapping and container."""

        widget = mapping.pop(workflow_id, None)
        if widget is None:
            return
        container.removeWidget(widget)
        widget.deleteLater()


__all__ = ["WorkflowClosureCoordinator", "WorkflowClosureView"]
