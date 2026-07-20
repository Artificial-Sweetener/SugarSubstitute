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

"""Resolve the workflow tab that receives an externally loaded document."""

from __future__ import annotations

from substitute.presentation.workflows.workflow_tabs_view import (
    workflow_tab_source_text,
)

from collections.abc import Callable, Mapping
from typing import Protocol

from substitute.application.workflows import is_default_workflow_tab_label


class WorkflowTabItem(Protocol):
    """Expose the tab item state needed for document targeting."""

    def routeKey(self) -> str:
        """Return the workflow session key."""

    def text(self) -> str:
        """Return the visible workflow label."""


class WorkflowTabBar(Protocol):
    """Expose active tab lookup needed for document targeting."""

    def currentIndex(self) -> int:
        """Return the active tab index."""

    def tabItem(self, index: int) -> WorkflowTabItem:
        """Return a tab item by index."""


class WorkflowSession(Protocol):
    """Expose workflow lookup and active identity for document targeting."""

    active_workflow_id: str
    workflows: Mapping[str, object]

    def get_workflow(self, workflow_id: str) -> object | None:
        """Return workflow state by id."""


class WorkflowDocumentTargetView(Protocol):
    """Expose session and tab state used by all document load paths."""

    workflow_tabbar: WorkflowTabBar
    workflow_session_service: WorkflowSession


class WorkflowDocumentTargetResolver:
    """Reuse one blank default tab or create a new target workflow."""

    def resolve(
        self,
        view: WorkflowDocumentTargetView,
        *,
        add_workflow_tab: Callable[[], object],
    ) -> str:
        """Return the workflow id that should receive an external document."""

        tab_item = view.workflow_tabbar.tabItem(view.workflow_tabbar.currentIndex())
        current_id = tab_item.routeKey()
        workflow = view.workflow_session_service.get_workflow(current_id)
        if _is_blank_default_workflow(workflow, workflow_tab_source_text(tab_item)):
            return current_id
        add_workflow_tab()
        return view.workflow_session_service.active_workflow_id


def _is_blank_default_workflow(workflow: object | None, tab_label: str) -> bool:
    """Return whether a workflow can safely receive a loaded document in place."""

    return bool(
        workflow is not None
        and not getattr(workflow, "stack_order", ())
        and not getattr(workflow, "cubes", {})
        and getattr(workflow, "direct_workflow", None) is None
        and is_default_workflow_tab_label(tab_label)
    )


__all__ = ["WorkflowDocumentTargetResolver", "WorkflowDocumentTargetView"]
