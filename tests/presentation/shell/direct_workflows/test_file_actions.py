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
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from substitute.application.direct_workflows import DirectWorkflowLoadService
from substitute.application.workflows.portable_model_projection import (
    PortableModelManifestService,
)
from substitute.application.recipes import RecipeModelDownloadResolutionError
from substitute.application.workflows import WorkflowTabService
from substitute.domain.common import JsonObject
from substitute.domain.workflow import WorkflowState
from substitute.infrastructure.comfy.workflow_document_repository import (
    ComfyWorkflowDocumentRepository,
)
from substitute.presentation.shell.direct_workflow_file_actions import (
    DirectWorkflowFileActions,
)
from substitute.presentation.shell.direct_workflow_composition import (
    compose_direct_workflow_file_actions,
)
from substitute.presentation.shell.direct_workflow_model_resolution import (
    DirectWorkflowModelResolutionController,
)
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowInvalidationReason,
    WorkflowSurface,
    WorkflowSurfaceInvalidationService,
)
from tests.support.passthrough_cube_analysis import PassthroughCubeWorkflowAnalyzer


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


def _view(workflow: WorkflowState, tab_item: _TabItem) -> SimpleNamespace:
    """Build the shell boundary required by direct-workflow file actions."""
    session = SimpleNamespace(
        active_workflow_id="wf-1",
        workflows={"wf-1": workflow},
        get_workflow=lambda _workflow_id: workflow,
    )
    return SimpleNamespace(
        workflow_session_service=session,
        workflow_tab_service=WorkflowTabService(),
        workflow_tabbar=_TabBar(tab_item),
        workflow_surface_invalidation_service=WorkflowSurfaceInvalidationService(),
    )


def _actions(
    *,
    view: SimpleNamespace,
    add_workflow_tab: Callable[[], None],
    refresh_active_workflow: Callable[[], None],
) -> DirectWorkflowFileActions:
    """Build file actions against the real loading service."""
    return DirectWorkflowFileActions(
        view=view,
        load_service=DirectWorkflowLoadService(
            ComfyWorkflowDocumentRepository(),
            PassthroughCubeWorkflowAnalyzer(),
        ),
        add_workflow_tab=add_workflow_tab,
        refresh_active_workflow=refresh_active_workflow,
    )


def test_direct_workflow_composition_defers_workspace_owned_model_controller() -> None:
    """Dependency capture must not read editor-busy state before workspace build."""

    shell = SimpleNamespace(
        cube_graph_gateway=PassthroughCubeWorkflowAnalyzer(),
        node_definition_gateway=None,
        create_recipe_model_load_resolver=lambda: None,
    )

    composition = compose_direct_workflow_file_actions(
        shell,
        manifest=cast(PortableModelManifestService, SimpleNamespace()),
        add_workflow_tab=lambda: None,
        workflow_workspace=SimpleNamespace(),
        error_presenter=cast(ErrorReportPresenterProtocol, SimpleNamespace()),
    )

    assert isinstance(composition.file_actions, DirectWorkflowFileActions)
    assert not hasattr(shell, "editor_busy")


def test_direct_workflow_file_action_loads_blank_tab_and_refreshes(
    tmp_path: Path,
) -> None:
    """Materialize a valid JSON document in the active blank tab."""
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
    view = _view(workflow, tab_item)
    refreshes: list[str] = []
    actions = _actions(
        view=view,
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
    invalidation = view.workflow_surface_invalidation_service
    dirty = invalidation.dirty_state("wf-1")
    assert WorkflowSurface.EDITOR in dirty.dirty_surfaces
    assert WorkflowSurface.CUBE_STACK in dirty.dirty_surfaces
    assert dirty.reasons == (WorkflowInvalidationReason.DIRECT_WORKFLOW_LOADED,)


def test_direct_workflow_file_action_rejects_non_workflow_json(
    tmp_path: Path,
) -> None:
    """Reject JSON without a Comfy UI graph without mutating workflow state."""
    source = tmp_path / "not-workflow.json"
    source.write_text('{"hello": "world"}', encoding="utf-8")
    workflow = WorkflowState()
    tab_item = _TabItem("wf-1", "Untitled Workflow")
    actions = _actions(
        view=_view(workflow, tab_item),
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
    """Validate before document loading mutates tab state."""
    source = tmp_path / "not-workflow.json"
    source.write_text('{"hello": "world"}', encoding="utf-8")
    workflow = WorkflowState()
    tab_item = _TabItem("wf-1", "Existing Document")
    added_tabs: list[str] = []
    actions = _actions(
        view=_view(workflow, tab_item),
        add_workflow_tab=lambda: added_tabs.append("added"),
        refresh_active_workflow=lambda: None,
    )

    assert actions.load_document(source) is None
    assert added_tabs == []


def test_model_download_failure_uses_specific_recoverable_error_copy(
    tmp_path: Path,
) -> None:
    """Explain model acquisition failure without misreporting malformed workflow JSON."""

    source = tmp_path / "portable-workflow.json"
    source.write_text('{"nodes": [], "links": []}', encoding="utf-8")
    workflow = WorkflowState()
    tab_item = _TabItem("wf-1", "Untitled Workflow")
    presented: list[dict[str, object]] = []
    failure = RecipeModelDownloadResolutionError("CivitAI API key was rejected.")
    controller = _FailingModelResolutionController(failure)
    actions = DirectWorkflowFileActions(
        view=_view(workflow, tab_item),
        load_service=DirectWorkflowLoadService(
            ComfyWorkflowDocumentRepository(),
            PassthroughCubeWorkflowAnalyzer(),
        ),
        add_workflow_tab=lambda: None,
        refresh_active_workflow=lambda: None,
        error_presenter=cast(
            ErrorReportPresenterProtocol,
            SimpleNamespace(
                show_exception_report=lambda **kwargs: presented.append(kwargs)
            ),
        ),
        model_resolution_controller_provider=lambda: cast(
            DirectWorkflowModelResolutionController, controller
        ),
    )

    assert actions.load_document(source) == "wf-1"
    assert len(presented) == 1
    assert presented[0]["title"] == "Model download failed"
    assert presented[0]["message"] == (
        "Substitute could not download and verify every model this workflow needs."
    )
    assert presented[0]["error"] is failure
    assert workflow.direct_workflow is None


def test_async_model_resolution_keeps_its_original_tab_target(tmp_path: Path) -> None:
    """A tab switch during model work must not redirect workflow materialization."""

    source = tmp_path / "portable-workflow.json"
    source.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "KSampler",
                        "inputs": [],
                        "outputs": [],
                        "widgets_values": [],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    target_workflow = WorkflowState()
    other_workflow = WorkflowState()
    target_tab = _TabItem("wf-1", "Untitled Workflow")
    other_tab = _TabItem("wf-2", "Other Workflow")
    view = _view(target_workflow, target_tab)
    view.workflow_session_service.workflows["wf-2"] = other_workflow
    view.workflow_tabbar.itemMap["wf-2"] = other_tab
    refreshes: list[str] = []
    controller = _DeferredModelResolutionController()
    actions = DirectWorkflowFileActions(
        view=view,
        load_service=DirectWorkflowLoadService(
            ComfyWorkflowDocumentRepository(),
            PassthroughCubeWorkflowAnalyzer(),
        ),
        add_workflow_tab=lambda: None,
        refresh_active_workflow=lambda: refreshes.append("refresh"),
        model_resolution_controller_provider=lambda: cast(
            DirectWorkflowModelResolutionController, controller
        ),
    )

    assert actions.load_document(source) == "wf-1"
    view.workflow_session_service.active_workflow_id = "wf-2"
    controller.complete()

    assert target_workflow.direct_workflow is not None
    assert other_workflow.direct_workflow is None
    assert target_tab.text() == "portable-workflow"
    assert other_tab.text() == "Other Workflow"
    assert refreshes == []


class _FailingModelResolutionController:
    """Report one deferred model download failure."""

    def __init__(self, error: BaseException) -> None:
        """Store the error delivered after canonical workflow reading."""

        self._error = error

    def resolve(
        self,
        *,
        workflow: object,
        target_workflow_id: str,
        completed: Callable[[object], None],
        cancelled: Callable[[], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Deliver the configured failure through the production callback path."""

        _ = (workflow, target_workflow_id, completed, cancelled)
        failed(self._error)


class _DeferredModelResolutionController:
    """Retain one completion callback until the test changes active tabs."""

    def __init__(self) -> None:
        """Initialize without a pending callback."""

        self._completed: Callable[[JsonObject], None] | None = None
        self._workflow: JsonObject | None = None

    def resolve(
        self,
        *,
        workflow: JsonObject,
        target_workflow_id: str,
        completed: Callable[[JsonObject], None],
        cancelled: Callable[[], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Retain the graph and production completion callback."""

        _ = (target_workflow_id, cancelled, failed)
        self._workflow = workflow
        self._completed = completed

    def complete(self) -> None:
        """Deliver the retained graph after the simulated tab switch."""

        assert self._completed is not None
        assert self._workflow is not None
        self._completed(self._workflow)
