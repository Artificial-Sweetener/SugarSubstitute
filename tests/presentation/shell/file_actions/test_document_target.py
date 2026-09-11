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

"""Verify loaded documents never replace workflow-owned canvas content."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.workflow_document_target import (
    WorkflowDocumentTargetResolver,
)


def test_loaded_document_preserves_masks_on_default_named_workflow() -> None:
    """A default tab with authored masks must remain an independent workflow."""

    workflow = WorkflowState()
    image_id = uuid4()
    mask_id = uuid4()
    workflow.canvas.bind_image("Region:source", image_id)
    collection = workflow.canvas.ensure_regional_mask_collection(
        ("Region", "load_mask_batch")
    )
    collection.add_region(image_id, mask_id=mask_id)
    tab_item = SimpleNamespace(
        routeKey=lambda: "main",
        text=lambda: "Untitled Workflow",
    )
    session = SimpleNamespace(
        active_workflow_id="main",
        workflows={"main": workflow},
        get_workflow=lambda workflow_id: {"main": workflow}.get(workflow_id),
    )
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
        ),
        workflow_session_service=session,
    )

    def add_workflow_tab() -> None:
        """Create the isolated destination selected by the production resolver."""

        session.active_workflow_id = "workflow-new"
        session.workflows["workflow-new"] = WorkflowState()

    target = WorkflowDocumentTargetResolver().resolve(
        view,
        add_workflow_tab=add_workflow_tab,
    )

    assert target == "workflow-new"
    assert workflow.canvas.image_entry("Region:source") is not None
    retained = workflow.canvas.regional_mask_collection(("Region", "load_mask_batch"))
    assert retained is not None
    assert retained.entries[0].mask_id == mask_id
