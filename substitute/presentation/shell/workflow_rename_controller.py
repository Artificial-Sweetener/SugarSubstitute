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

"""Rename workflow labels while preserving immutable workflow identity."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from substitute.application.workflows import WorkflowSessionService, WorkflowTabService
from substitute.application.workflows.project_asset_owner_service import (
    ProjectAssetOwnerService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.workflows.workflow_tabs_view import (
    set_workflow_tab_source_text,
    workflow_tab_source_text,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.shell.workflow_rename_controller")


class WorkflowRenameTabBar(Protocol):
    """Describe workflow tab lookup needed for rename actions."""

    itemMap: Mapping[str, object]


class WorkflowRenameView(Protocol):
    """Describe application and tab state required to rename a workflow."""

    workflow_tab_service: WorkflowTabService
    workflow_session_service: WorkflowSessionService[object]
    workflow_tabbar: WorkflowRenameTabBar


class WorkflowRenameController:
    """Own workflow display-label validation, mutation, and dirty state."""

    def __init__(self, view: WorkflowRenameView) -> None:
        """Store the shell view containing tab and workflow state."""

        self._view = view

    def rename_workflow(self, workflow_id: str, proposed_name: str) -> None:
        """Rename one workflow label without changing its immutable identity."""

        view = self._view
        tab_item = view.workflow_tabbar.itemMap.get(workflow_id)
        if tab_item is None:
            return
        old_label = workflow_tab_source_text(tab_item)
        existing_labels = {
            workflow_tab_source_text(item)
            for other_workflow_id, item in view.workflow_tabbar.itemMap.items()
            if other_workflow_id != workflow_id
        }
        decision = view.workflow_tab_service.resolve_inline_rename(
            old_workflow_id=workflow_id,
            proposed_name=proposed_name,
            existing_labels=existing_labels,
        )
        if not decision.accepted:
            set_workflow_tab_source_text(tab_item, old_label)
            return
        if old_label == decision.tab_label:
            return
        workflow = view.workflow_session_service.get_workflow(workflow_id)
        if isinstance(workflow, WorkflowState):
            ProjectAssetOwnerService().pin_legacy_owners(
                workflow,
                storage_owner=old_label,
            )
        set_workflow_tab_source_text(tab_item, decision.tab_label)
        unsaved_work_service = getattr(view, "unsaved_work_service", None)
        mark_document_dirty = getattr(unsaved_work_service, "mark_dirty", None)
        if callable(mark_document_dirty):
            mark_document_dirty(workflow_id)
        log_info(
            _LOGGER,
            "Renamed workflow display label without changing identity",
            workflow_id=workflow_id,
            old_label=old_label,
            new_label=decision.tab_label,
        )


__all__ = ["WorkflowRenameController", "WorkflowRenameView"]
