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

"""Typed local doubles for MainWindow Input-canvas composition contracts."""

from __future__ import annotations

from pathlib import Path


class _Signal:
    """Record connected slots for signal-composition tests."""

    def __init__(self) -> None:
        """Initialize with no connected slots."""

        self.connected: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""

        self.connected.append(slot)


class _FakeSignal(_Signal):
    """Alias signal fake for readability in input-canvas composition tests."""


class _FakeInputCanvasToolController:
    """Capture canvas-tool activation controller wiring inputs."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs

    def synchronize_native_tool(self, _tool_id: str) -> None:
        """Accept native mode synchronization wiring."""

    def request_tool(self, _tool_id: str) -> bool:
        """Accept requested tool wiring."""

        return True

    def restore_operation(self, _operation_id: str) -> bool:
        """Accept persisted operation restoration wiring."""

        return True


class _FakeInputCanvasInteractionProfileService:
    """Capture workflow interaction-profile service wiring."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor dependencies for assertions."""

        self.kwargs = kwargs

    def profile_for(self, _workflow: object, _image_id: object) -> object:
        """Return an inert profile value for captured controller wiring."""

        return object()


class _FakeInputCanvasToolProfileController:
    """Capture workflow-aware Input tool projection wiring."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor dependencies and initialize refresh history."""

        self.kwargs = kwargs
        self.refresh_calls = 0

    def refresh_document_context(self) -> bool:
        """Record one document-context projection refresh."""

        self.refresh_calls += 1
        return True

    def refresh_workflow_profile(self) -> bool:
        """Record one workflow-profile projection refresh."""

        self.refresh_calls += 1
        return True

    def close(self) -> None:
        """Accept Input surface teardown wiring."""


class _FakeInputCanvasShellAdapter:
    """Provide shell adapter callbacks for input-canvas composition."""

    def __init__(self, shell: object) -> None:
        """Keep the owning shell for assertions."""

        self.shell = shell
        self.resolve_workflow_name = object()
        self.mark_input_canvas_changed = object()
        self.mark_input_canvas_presentation_changed = object()


class _FakeInputCanvasPresenter:
    """Capture presenter wiring and mask-picker refresh requests."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs
        self.refreshed_masks: list[tuple[object, object]] = []

    def materialize_image_selection(self, *_args: object) -> bool:
        """Accept image materialization for interaction composition."""

        return True

    def apply_mask_selection(self, *_args: object) -> bool:
        """Accept mask materialization for interaction composition."""

        return True

    def refresh_active_mask_pickers(self) -> None:
        """Represent the presenter-owned picker refresh callback."""

    def refresh_mask_picker_from_asset_state(
        self,
        cube_alias: object,
        node_name: object,
    ) -> None:
        """Record a saved-mask refresh routed from the save controller."""

        self.refreshed_masks.append((cube_alias, node_name))


class _FakeInputDocumentChangeObserver:
    """Capture in-memory document change observer wiring."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _FakeInputNodeInteractionController:
    """Capture single-owner Input-node interaction composition."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor collaborators for assertions."""

        self.kwargs = kwargs


class _FakeWorkflowInputCanvasService:
    """Capture workflow input-canvas service dependencies."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _FakeInputCanvasCapabilityService:
    """Capture input-canvas capability service dependency."""

    def __init__(
        self,
        input_canvas_plan_service: object,
        graph_section_service: object,
    ) -> None:
        """Store canvas planning and graph section services for assertions."""

        self.input_canvas_plan_service = input_canvas_plan_service
        self.graph_section_service = graph_section_service


class _FakeSyntheticCanvasGeometryAdapter:
    """Capture the native canvas selected for synthetic geometry work."""

    def __init__(self, canvas: object, parent: object) -> None:
        """Store the canvas and QObject parent supplied by composition."""

        self.canvas = canvas
        self.parent = parent


class _FakeSyntheticCanvasResolutionController:
    """Capture shell orchestration collaborators for synthetic resolution."""

    def __init__(self, **kwargs: object) -> None:
        """Store constructor keyword arguments for assertions."""

        self.kwargs = kwargs


class _ParentedValue:
    """Record the parent supplied to a composed Qt-adjacent value."""

    def __init__(self, parent: object) -> None:
        """Store the owner used for lifetime management."""

        self.parent = parent


class _SceneMappingChanges(_ParentedValue):
    """Provide the mapping-change signal owned by the canvas scene."""

    def __init__(self, parent: object) -> None:
        """Initialize the parent relationship and observable change signal."""

        super().__init__(parent)
        self.changed = _FakeSignal()


class _ToolRuntime:
    """Capture tool-option and action registrations from composition."""

    def __init__(self, palette: object) -> None:
        """Initialize runtime state with the supplied visual palette."""

        self.palette = palette
        self.registered_options: dict[object, object] = {}
        self.registered_actions: list[tuple[object, object]] = []

    def register_options(self, options_id: object, factory: object) -> None:
        """Record one contextual options factory."""

        self.registered_options[options_id] = factory

    def register_action(self, contribution: object, handler: object) -> None:
        """Record one contextual toolbar action."""

        self.registered_actions.append((contribution, handler))


class _ToolContext:
    """Provide the document tool context consumed by the profile controller."""

    def __init__(self, activate_transform: object) -> None:
        """Initialize the transform activator and context-change signal."""

        self.activate_transform = activate_transform
        self.changed = _FakeSignal()


class _ToolOptions:
    """Provide clearable Input-canvas selection option callbacks."""

    def clear_pixel_selection(self) -> bool:
        """Report a successful pixel-selection clear request."""

        return True

    def clear_selected_pixels(self) -> bool:
        """Report a successful selected-pixels clear request."""

        return True


class _GenerationCapture:
    """Expose a stable capture callback for generation snapshot wiring."""

    def __init__(self) -> None:
        """Initialize the opaque capture callback token."""

        self.capture = object()


class _DocumentCanvas:
    """Provide scene signals consumed by Input-canvas composition."""

    def __init__(self) -> None:
        """Initialize the scene change signals."""

        self.sceneEditHistoryChanged = _FakeSignal()
        self.compositionChanged = _FakeSignal()


class _InputDocument:
    """Provide the explicit document contract required by composition."""

    def __init__(self, tool_context: _ToolContext) -> None:
        """Initialize document callbacks, state tokens, and change signals."""

        self.canvas = _DocumentCanvas()
        self.set_canvas_operation = object()
        self.current_canvas_operation = object()
        self.export_mask_image = object()
        self.generation_capture = _GenerationCapture()
        self.editable_persistence = object()
        self.tool_options = _ToolOptions()
        self.preview_bindings = object()
        self.tool_context = tool_context
        self.canvasToolChanged = _FakeSignal()
        self.maskContentChanged = _FakeSignal()
        self.activeMaskChanged = _FakeSignal()


class _InputCanvasWidget:
    """Provide the widget-level signal used by Input-canvas composition."""

    def __init__(self) -> None:
        """Initialize the mask undo-stack signal token."""

        self.maskUndoStackChanged = object()


class _InputCanvas:
    """Provide the Input canvas's focused composition contract."""

    def __init__(self, document: _InputDocument) -> None:
        """Initialize document access, runtime binding, and widget signals."""

        self.document = document
        self.canvas = _InputCanvasWidget()
        self.current_image_id_for_event = object()
        self.bound_runtimes: list[tuple[object, object, object]] = []
        self.toolRequested = _FakeSignal()
        self.destroyed = _FakeSignal()

    def bind_tool_runtime(
        self,
        runtime: object,
        layout: object,
        *,
        restore_operation: object,
    ) -> None:
        """Record one runtime binding and its restoration callback."""

        self.bound_runtimes.append((runtime, layout, restore_operation))


class _CanvasHost:
    """Resolve the single Input canvas required by this contract test."""

    def __init__(self, input_canvas: _InputCanvas) -> None:
        """Store the Input canvas route target."""

        self.input_canvas = input_canvas

    def canvas_for(self, route_key: str) -> _InputCanvas | None:
        """Return the Input canvas only for the Input route."""

        if route_key == "Input":
            return self.input_canvas
        return None


class _WorkflowSession:
    """Provide the active workflow lookup consumed by profile composition."""

    def __init__(self) -> None:
        """Initialize the active workflow and its identifier."""

        self.active_workflow_id = "workflow-a"
        self.active_workflow = object()
        self.workflows = {self.active_workflow_id: self.active_workflow}


class _PathBundle:
    """Provide the two paths owned by the Input-canvas composition slice."""

    def __init__(self) -> None:
        """Initialize deterministic project and session paths."""

        self.projects_dir = Path("E:/projects")
        self.session_dir = Path("E:/session")


class _InputCompositionShell:
    """Provide the explicit shell contract for Input-canvas composition."""

    def __init__(self) -> None:
        """Initialize the services and state read by composition."""

        tool_context = _ToolContext(object())
        self.input_canvas = _InputCanvas(_InputDocument(tool_context))
        self.canvas_host = _CanvasHost(self.input_canvas)
        self.input_canvas_plan_service = object()
        self.input_asset_endpoint_service = object()
        self.graph_section_service = object()
        self.input_canvas_state_service = object()
        self.canvas_io_service = object()
        self.workflow_asset_service = object()
        self.workflow_session_service = _WorkflowSession()
        self.path_bundle = _PathBundle()
        self.active_workflow = object()
        self.active_editor_panel = object()
        self._error_presenter = object()
        self.request_session_autosave = object()
        self.workflow_input_canvas_service: object | None = None
        self.input_canvas_presenter: object | None = None
        self.input_node_interaction_controller: object | None = None
        self.input_document_change_observer: object | None = None
        self.input_generation_snapshot_service: object | None = None

    def get_active_workflow(self) -> object:
        """Return the stable active workflow used by composition callbacks."""

        return self.active_workflow
