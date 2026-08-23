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

"""Verify MainWindow Input-canvas composition."""

from __future__ import annotations

import pytest

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.shell import input_canvas_composition
from tests.presentation.shell.main_window.input_canvas.support import (
    _FakeInputCanvasCapabilityService,
    _FakeInputCanvasInteractionProfileService,
    _FakeInputCanvasPresenter,
    _FakeInputCanvasShellAdapter,
    _FakeInputCanvasToolController,
    _FakeInputCanvasToolProfileController,
    _FakeInputDocumentChangeObserver,
    _FakeInputNodeInteractionController,
    _FakeSyntheticCanvasGeometryAdapter,
    _FakeSyntheticCanvasResolutionController,
    _FakeWorkflowInputCanvasService,
    _InputCompositionShell,
    _ParentedValue,
    _SceneMappingChanges,
    _ToolRuntime,
)


def test_compose_input_canvas_controllers_assigns_presenter_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure Input canvas presenter composition stays outside MainWindow.__init__."""

    monkeypatch.setattr(
        input_canvas_composition,
        "WorkflowInputCanvasService",
        _FakeWorkflowInputCanvasService,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputCanvasToolController",
        _FakeInputCanvasToolController,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputCanvasInteractionProfileService",
        _FakeInputCanvasInteractionProfileService,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputCanvasToolProfileController",
        _FakeInputCanvasToolProfileController,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputSharedEdgeResizePolicy",
        lambda _canvas, *, parent: _ParentedValue(parent),
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputSceneMappingChanges",
        lambda _canvas, *, parent: _SceneMappingChanges(parent),
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputCanvasShellAdapter",
        _FakeInputCanvasShellAdapter,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputCanvasPresenter",
        _FakeInputCanvasPresenter,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputNodeInteractionController",
        _FakeInputNodeInteractionController,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputDocumentChangeObserver",
        _FakeInputDocumentChangeObserver,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "InputCanvasCapabilityService",
        _FakeInputCanvasCapabilityService,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "SyntheticCanvasGeometryAdapter",
        _FakeSyntheticCanvasGeometryAdapter,
    )
    monkeypatch.setattr(
        input_canvas_composition,
        "SyntheticCanvasResolutionController",
        _FakeSyntheticCanvasResolutionController,
    )
    runtime = _ToolRuntime(palette=object())
    monkeypatch.setattr(
        input_canvas_composition,
        "create_input_canvas_tool_system",
        lambda: runtime,
    )
    shell = _InputCompositionShell()
    input_canvas = shell.input_canvas
    document = input_canvas.document
    tool_context = document.tool_context

    composition = input_canvas_composition.compose_input_canvas_controllers(shell)

    assert isinstance(
        composition.workflow_input_canvas_service,
        _FakeWorkflowInputCanvasService,
    )
    assert isinstance(
        composition.input_canvas_tool_controller,
        _FakeInputCanvasToolController,
    )
    assert isinstance(
        composition.input_canvas_tool_profile_controller,
        _FakeInputCanvasToolProfileController,
    )
    assert isinstance(
        composition.input_canvas_shell_adapter, _FakeInputCanvasShellAdapter
    )
    assert isinstance(composition.input_canvas_presenter, _FakeInputCanvasPresenter)
    assert isinstance(
        composition.input_document_change_observer,
        _FakeInputDocumentChangeObserver,
    )
    assert isinstance(
        composition.input_canvas_capability_service,
        _FakeInputCanvasCapabilityService,
    )
    assert isinstance(
        composition.synthetic_canvas_geometry_adapter,
        _FakeSyntheticCanvasGeometryAdapter,
    )
    assert isinstance(
        composition.synthetic_canvas_resolution_controller,
        _FakeSyntheticCanvasResolutionController,
    )
    assert (
        composition.workflow_input_canvas_service is shell.workflow_input_canvas_service
    )
    assert composition.input_canvas_presenter is shell.input_canvas_presenter
    assert (
        composition.input_node_interaction_controller
        is shell.input_node_interaction_controller
    )
    assert (
        composition.input_document_change_observer
        is shell.input_document_change_observer
    )
    assert (
        composition.input_generation_snapshot_service
        is shell.input_generation_snapshot_service
    )
    assert composition.workflow_input_canvas_service.kwargs == {
        "input_canvas_plan_service": shell.input_canvas_plan_service,
        "input_canvas_state_service": shell.input_canvas_state_service,
        "canvas_io_service": shell.canvas_io_service,
        "workflow_asset_service": shell.workflow_asset_service,
        "graph_section_service": shell.graph_section_service,
    }
    assert composition.input_canvas_tool_controller.kwargs == {
        "transform_activator": tool_context.activate_transform,
        "operation_setter": document.set_canvas_operation,
        "current_operation_provider": document.current_canvas_operation,
        "runtime": runtime,
        "layout": input_canvas.bound_runtimes[0][1],
    }
    profile_kwargs = composition.input_canvas_tool_profile_controller.kwargs
    assert profile_kwargs["document_context"] is tool_context
    active_workflow_provider = profile_kwargs["active_workflow"]
    assert callable(active_workflow_provider)
    assert (
        active_workflow_provider()
        is (shell.workflow_session_service.workflows["workflow-a"])
    )
    profile_callback = profile_kwargs["interaction_profile"]
    assert isinstance(
        getattr(profile_callback, "__self__", None),
        _FakeInputCanvasInteractionProfileService,
    )
    assert profile_kwargs["palette"] is runtime.palette
    assert profile_kwargs["activation"] is composition.input_canvas_tool_controller
    assert input_canvas.bound_runtimes[0][0] is runtime
    assert (
        input_canvas.bound_runtimes[0][2]
        == composition.input_canvas_tool_controller.restore_operation
    )
    assert [
        getattr(contribution, "tool_id")
        for contribution, _handler in runtime.registered_actions
    ] == [
        InputCanvasToolId.DESELECT,
        InputCanvasToolId.CLEAR_SELECTION_PIXELS,
    ]
    assert tool_context.changed.connected == [
        composition.input_canvas_tool_profile_controller.refresh_document_context
    ]
    assert document.canvasToolChanged.connected == [
        composition.input_canvas_tool_controller.synchronize_native_tool
    ]
    assert input_canvas.destroyed.connected == [
        composition.input_canvas_tool_profile_controller.close
    ]
    assert input_canvas.toolRequested.connected == [
        composition.input_canvas_tool_controller.request_tool
    ]
    assert composition.input_canvas_tool_profile_controller.refresh_calls == 1
    assert composition.input_canvas_shell_adapter.shell is shell
    assert composition.input_canvas_presenter.kwargs["input_document"] is document
    assert (
        composition.input_canvas_presenter.kwargs["workflow_input_canvas_service"]
        is composition.workflow_input_canvas_service
    )
    assert (
        composition.input_canvas_presenter.kwargs["workflow_name_provider"]
        is composition.input_canvas_shell_adapter.resolve_workflow_name
    )
    assert (
        composition.input_canvas_presenter.kwargs["mark_canvas_changed"]
        is composition.input_canvas_shell_adapter.mark_input_canvas_changed
    )
    assert composition.input_document_change_observer.kwargs == {
        "changes": (
            document.maskContentChanged,
            composition.input_scene_mapping_changes.changed,
        ),
        "active_workflow_id": (
            composition.input_document_change_observer.kwargs["active_workflow_id"]
        ),
        "mark_workflow_changed": (
            composition.input_canvas_shell_adapter.mark_input_canvas_changed
        ),
        "request_autosave": shell.request_session_autosave,
    }
    active_workflow_id_provider = composition.input_document_change_observer.kwargs[
        "active_workflow_id"
    ]
    assert callable(active_workflow_id_provider)
    assert active_workflow_id_provider() == "workflow-a"
    assert (
        composition.input_canvas_capability_service.input_canvas_plan_service
        is shell.input_canvas_plan_service
    )
    assert (
        composition.input_canvas_capability_service.graph_section_service
        is shell.graph_section_service
    )
    assert composition.synthetic_canvas_geometry_adapter.canvas is document.canvas
    assert (
        composition.synthetic_canvas_resolution_controller.kwargs["geometry"]
        is composition.synthetic_canvas_geometry_adapter
    )
    assert (
        composition.synthetic_canvas_resolution_controller.kwargs["roles"]
        is composition.synthetic_canvas_resolution_role_service
    )
