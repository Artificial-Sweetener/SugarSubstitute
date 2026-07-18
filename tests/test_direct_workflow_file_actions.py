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

"""Verify shell materialization of direct Comfy workflow documents."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.application.workflows import WorkflowTabService
from substitute.domain.workflow import WorkflowState
from substitute.infrastructure.comfy.workflow_json_repository import (
    JsonComfyWorkflowRepository,
)
from substitute.presentation.shell.direct_workflow_file_actions import (
    DirectWorkflowFileActions,
)
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)


class _TabItem:
    """Expose the shell tab operations used by document loading."""

    def __init__(self, route_key: str, text: str) -> None:
        """Store route identity and visible label."""

        self._route_key = route_key
        self._text = text

    def routeKey(self) -> str:
        """Return the stable workflow session key."""

        return self._route_key

    def text(self) -> str:
        """Return the visible tab label."""

        return self._text

    def setText(self, text: str) -> None:
        """Replace the visible tab label."""

        self._text = text


class _TabBar:
    """Expose one active workflow tab."""

    def __init__(self, item: _TabItem) -> None:
        """Store the active item and route lookup."""

        self._item = item
        self.itemMap = {item.routeKey(): item}

    def currentIndex(self) -> int:
        """Return the only tab index."""

        return 0

    def tabItem(self, index: int) -> _TabItem:
        """Return the only tab item."""

        assert index == 0
        return self._item


def test_direct_workflow_file_action_loads_blank_tab_and_refreshes(
    tmp_path: Path,
) -> None:
    """A valid JSON document should become the active tab's editor source."""

    source = tmp_path / "Portrait Workflow.json"
    source.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "KSampler",
                        "inputs": [
                            {
                                "name": "seed",
                                "type": "INT",
                                "widget": {"name": "seed"},
                                "link": None,
                            }
                        ],
                        "outputs": [],
                        "widgets_values": [12],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    workflow = WorkflowState()
    tab_item = _TabItem("wf-1", "Untitled Workflow")
    tabbar = _TabBar(tab_item)
    session = SimpleNamespace(
        active_workflow_id="wf-1",
        workflows={"wf-1": workflow},
        get_workflow=lambda workflow_id: {"wf-1": workflow}.get(workflow_id),
    )
    invalidation = WorkflowSurfaceInvalidationService()
    view = SimpleNamespace(
        workflow_session_service=session,
        workflow_tab_service=WorkflowTabService(),
        workflow_tabbar=tabbar,
        workflow_surface_invalidation_service=invalidation,
    )
    refreshes: list[str] = []
    actions = DirectWorkflowFileActions(
        view=view,
        load_service=DirectWorkflowLoadService(JsonComfyWorkflowRepository()),
        add_workflow_tab=lambda: None,
        refresh_active_workflow=lambda: refreshes.append("refresh"),
    )

    workflow_id = actions.load_document(source)

    assert workflow_id == "wf-1"
    assert workflow.direct_workflow is not None
    assert workflow.direct_workflow.buffer["nodes"]["1"]["inputs"] == {  # type: ignore[index]
        "seed": 12
    }
    assert tab_item.text() == "Portrait Workflow"
    assert refreshes == ["refresh"]
    dirty = invalidation.dirty_state("wf-1")
    assert WorkflowSurface.EDITOR in dirty.dirty_surfaces
    assert dirty.reasons == (WorkflowInvalidationReason.DIRECT_WORKFLOW_LOADED,)


def test_direct_workflow_file_action_rejects_non_workflow_json(
    tmp_path: Path,
) -> None:
    """JSON without a Comfy UI graph should not mutate the workflow state."""

    source = tmp_path / "not-workflow.json"
    source.write_text('{"hello": "world"}', encoding="utf-8")
    workflow = WorkflowState()
    tab_item = _TabItem("wf-1", "Untitled Workflow")
    session = SimpleNamespace(
        active_workflow_id="wf-1",
        workflows={"wf-1": workflow},
        get_workflow=lambda _workflow_id: workflow,
    )
    view = SimpleNamespace(
        workflow_session_service=session,
        workflow_tab_service=WorkflowTabService(),
        workflow_tabbar=_TabBar(tab_item),
        workflow_surface_invalidation_service=WorkflowSurfaceInvalidationService(),
    )
    actions = DirectWorkflowFileActions(
        view=view,
        load_service=DirectWorkflowLoadService(JsonComfyWorkflowRepository()),
        add_workflow_tab=lambda: None,
        refresh_active_workflow=lambda: None,
    )

    workflow_id = actions.load_document(source)

    assert workflow_id is None
    assert workflow.direct_workflow is None
    assert tab_item.text() == "Untitled Workflow"


def test_invalid_direct_workflow_does_not_create_a_target_tab(
    tmp_path: Path,
) -> None:
    """Validation should finish before document loading mutates tab state."""

    source = tmp_path / "not-workflow.json"
    source.write_text('{"hello": "world"}', encoding="utf-8")
    workflow = WorkflowState()
    tab_item = _TabItem("wf-1", "Existing Document")
    session = SimpleNamespace(
        active_workflow_id="wf-1",
        workflows={"wf-1": workflow},
        get_workflow=lambda _workflow_id: workflow,
    )
    view = SimpleNamespace(
        workflow_session_service=session,
        workflow_tab_service=WorkflowTabService(),
        workflow_tabbar=_TabBar(tab_item),
        workflow_surface_invalidation_service=WorkflowSurfaceInvalidationService(),
    )
    added_tabs: list[str] = []
    actions = DirectWorkflowFileActions(
        view=view,
        load_service=DirectWorkflowLoadService(JsonComfyWorkflowRepository()),
        add_workflow_tab=lambda: added_tabs.append("added"),
        refresh_active_workflow=lambda: None,
    )

    assert actions.load_document(source) is None
    assert added_tabs == []
