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

"""Verify Input-specific policy over the reusable canvas tool system."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from PySide6.QtGui import QIcon
from cutecanvas import CuteCanvas, EditorTransformTarget
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
)

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    BRUSH_OPTIONS_ID,
    INPUT_IMAGE_CAPABILITY,
    INPUT_CANVAS_CONTEXT_TAGS,
    INPUT_RASTER_ANALYSIS_CONTEXT,
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.tools.model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolSurface,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon
from tests.support.input_canvas.tool_context_projection import (
    project_authored_input_tool_context,
)


@dataclass
class _ToolDocument:
    """Expose mutable Input tool context to the controller."""

    has_mask: bool = False
    sam_ready: bool = False
    has_selection: bool = False
    transform_available: bool = False
    layer_content_available: bool = True
    clear_available: bool = False
    current_operation_id: str | None = CuteCanvas.CONTROL_MODE_PANZOOM
    transform_target: EditorTransformTarget | None = None
    image_id: UUID | None = None

    @property
    def snapshot(self) -> InputCanvasToolContextSnapshot:
        """Return current semantic capability state."""

        return InputCanvasToolContextSnapshot(
            image_id=self.image_id,
            has_active_mask=self.has_mask,
            smart_segmentation_ready=self.sam_ready,
            has_pixel_selection=self.has_selection,
            selection_transform_available=self.transform_available,
            layer_transform_available=self.layer_content_available,
            selection_clear_available=self.clear_available,
            edit_session_active=False,
        )

    def activate_transform(self, target: EditorTransformTarget) -> bool:
        """Record explicit affine target activation."""
        self.transform_target = target
        self.current_operation_id = CuteCanvas.CONTROL_MODE_TRANSFORM
        return True


def _transform_target(document: _ToolDocument) -> EditorTransformTarget | None:
    """Return the fake document target without retaining assertion narrowing."""

    return document.transform_target


def _controller(
    document: _ToolDocument,
    *,
    image_id: UUID | None,
    accepted: bool = True,
) -> tuple[InputCanvasToolController, list[str]]:
    """Return one controller and its applied tool IDs."""

    runtime = create_input_canvas_tool_system()
    applied: list[str] = []
    document.image_id = image_id

    def apply(operation_id: str) -> bool:
        """Record an accepted mode and update the fake native state."""

        applied.append(operation_id)
        if accepted:
            document.current_operation_id = operation_id
        return accepted

    return (
        InputCanvasToolController(
            transform_activator=document.activate_transform,
            operation_setter=apply,
            current_operation_provider=lambda: document.current_operation_id,
            runtime=runtime,
        ),
        applied,
    )


def test_input_catalog_has_expected_editor_order_and_tool_kinds() -> None:
    """The built-in palette should establish the current editor ordering."""

    palette = create_input_canvas_tool_system().palette
    palette.set_context(
        CanvasToolContext(
            tags=INPUT_CANVAS_CONTEXT_TAGS.union({INPUT_RASTER_ANALYSIS_CONTEXT})
        )
    )

    assert tuple(
        item.tool_id for item in palette.snapshot(CanvasToolSurface.TOOL_STRIP)
    ) == (
        InputCanvasToolId.MOVE,
        InputCanvasToolId.SHARED_EDGE_RESIZE,
        InputCanvasToolId.TRANSFORM_LAYER,
        InputCanvasToolId.SELECT_RECTANGLE,
        InputCanvasToolId.SELECT_ELLIPSE,
        InputCanvasToolId.SELECT_LASSO,
        InputCanvasToolId.SMART_SELECT,
        InputCanvasToolId.MASK_RECTANGLE,
        InputCanvasToolId.MASK_ELLIPSE,
        InputCanvasToolId.MASK_LASSO,
        InputCanvasToolId.SMART_MASK,
        InputCanvasToolId.BRUSH,
        InputCanvasToolId.ERASER,
        InputCanvasToolId.PAN_ZOOM,
    )
    assert tuple(
        item.tool_id for item in palette.snapshot(CanvasToolSurface.CONTEXTUAL_TOOLBAR)
    ) == (InputCanvasToolId.TRANSFORM_SELECTION,)


def test_transform_routes_choose_explicit_targets() -> None:
    """Contextual and normal-strip entries must share mode but not target authority."""
    document = _ToolDocument(
        has_mask=True,
        has_selection=True,
        transform_available=True,
    )
    controller, _applied = _controller(document, image_id=uuid4())
    project_authored_input_tool_context(controller, document)

    assert controller.request_tool(InputCanvasToolId.TRANSFORM_SELECTION)
    assert _transform_target(document) is EditorTransformTarget.SELECTION_CONTENT

    document.current_operation_id = CuteCanvas.CONTROL_MODE_PANZOOM
    project_authored_input_tool_context(controller, document)
    assert controller.request_tool(InputCanvasToolId.TRANSFORM_LAYER)
    assert _transform_target(document) is EditorTransformTarget.LAYER_CONTENT


def test_eraser_is_a_distinct_mode_with_shared_brush_options() -> None:
    """Eraser should share brush presentation without sharing mode semantics."""

    runtime = create_input_canvas_tool_system()
    eraser = runtime.registry.contribution(InputCanvasToolId.ERASER)
    brush = runtime.registry.contribution(InputCanvasToolId.BRUSH)

    assert eraser is not None
    assert brush is not None
    assert eraser.document_operation_id == CuteCanvas.CONTROL_MODE_ERASER
    assert eraser.options_id == BRUSH_OPTIONS_ID == brush.options_id
    assert eraser.icon is AppIcon.ERASER_20_REGULAR
    assert eraser.document_operation_id != brush.document_operation_id


def test_transform_surfaces_share_a_distinct_transform_icon() -> None:
    """Transform must not reuse the Move tool's four-direction arrow glyph."""

    palette = create_input_canvas_tool_system().palette
    palette.set_context(
        CanvasToolContext(
            tags=INPUT_CANVAS_CONTEXT_TAGS.union({INPUT_RASTER_ANALYSIS_CONTEXT})
        )
    )
    move = palette.presentation_for(InputCanvasToolId.MOVE)
    layer_transform = palette.presentation_for(InputCanvasToolId.TRANSFORM_LAYER)
    selection_transform = palette.presentation_for(
        InputCanvasToolId.TRANSFORM_SELECTION
    )

    assert move is not None
    assert layer_transform is not None
    assert selection_transform is not None
    assert move.icon is AppIcon.ARROW_MOVE_20_REGULAR
    assert layer_transform.icon is AppIcon.SELECT_OBJECT_SKEW_20_REGULAR
    assert selection_transform.icon is AppIcon.SELECT_OBJECT_SKEW_20_REGULAR


def test_shared_edge_resize_uses_fluent_resize_icon_and_public_native_mode() -> None:
    """The built-in should present and activate the public CuteCanvas operation."""

    document = _ToolDocument(has_mask=True)
    controller, applied = _controller(document, image_id=uuid4())
    project_authored_input_tool_context(controller, document)
    resize = controller.palette.presentation_for(InputCanvasToolId.SHARED_EDGE_RESIZE)

    assert resize is not None and resize.enabled
    assert resize.icon is AppIcon.ARROW_AUTOFIT_WIDTH_20_REGULAR
    assert controller.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)
    assert applied == [CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE]


def test_selection_and_mask_shape_families_use_distinct_icons() -> None:
    """Different authoring semantics must remain recognizable in grouped slots."""

    palette = create_input_canvas_tool_system().palette
    palette.set_context(
        CanvasToolContext(
            tags=INPUT_CANVAS_CONTEXT_TAGS.union({INPUT_RASTER_ANALYSIS_CONTEXT})
        )
    )
    icons = {
        item.tool_id: item.icon
        for item in palette.snapshot(CanvasToolSurface.TOOL_STRIP)
    }

    assert (
        icons[InputCanvasToolId.SELECT_RECTANGLE]
        != icons[InputCanvasToolId.MASK_RECTANGLE]
    )
    assert (
        icons[InputCanvasToolId.SELECT_ELLIPSE] != icons[InputCanvasToolId.MASK_ELLIPSE]
    )
    assert icons[InputCanvasToolId.SELECT_LASSO] != icons[InputCanvasToolId.MASK_LASSO]
    assert icons[InputCanvasToolId.SMART_SELECT] not in {
        icons[InputCanvasToolId.MASK_RECTANGLE],
        icons[InputCanvasToolId.MASK_ELLIPSE],
        icons[InputCanvasToolId.MASK_LASSO],
    }
    assert icons[InputCanvasToolId.SMART_SELECT] is AppIcon.SMART_SELECT_20_REGULAR
    assert icons[InputCanvasToolId.SMART_MASK] is AppIcon.SMART_MASK_20_REGULAR
    assert (
        icons[InputCanvasToolId.SMART_SELECT] is not icons[InputCanvasToolId.SMART_MASK]
    )


def test_selection_transform_capabilities_derive_from_document_state() -> None:
    """Transform must require both selection content and editor authorization."""
    image_id = uuid4()
    document = _ToolDocument()
    controller, _applied = _controller(document, image_id=image_id)

    project_authored_input_tool_context(controller, document)
    transform = controller.palette.presentation_for(
        InputCanvasToolId.TRANSFORM_SELECTION
    )
    assert transform is not None and not transform.enabled

    document.has_selection = True
    project_authored_input_tool_context(controller, document)
    transform = controller.palette.presentation_for(
        InputCanvasToolId.TRANSFORM_SELECTION
    )
    assert transform is not None and not transform.enabled

    document.transform_available = True
    project_authored_input_tool_context(controller, document)
    transform = controller.palette.presentation_for(
        InputCanvasToolId.TRANSFORM_SELECTION
    )
    assert transform is not None and transform.enabled


def test_empty_layer_disables_transform_with_an_owned_explanation() -> None:
    """The layer tool must expose CuteCanvas content denial without guessing."""
    document = _ToolDocument(has_mask=True, layer_content_available=False)
    controller, _applied = _controller(document, image_id=uuid4())

    project_authored_input_tool_context(controller, document)

    transform = controller.palette.presentation_for(InputCanvasToolId.TRANSFORM_LAYER)
    assert transform is not None and not transform.enabled
    assert transform.unavailable_reason is not None
    assert (
        render_application_text(transform.unavailable_reason) == "Nothing to transform!"
    )

    document.layer_content_available = True
    project_authored_input_tool_context(controller, document)
    transform = controller.palette.presentation_for(InputCanvasToolId.TRANSFORM_LAYER)
    assert transform is not None and transform.enabled
    assert transform.unavailable_reason is None


def test_input_context_enables_navigation_then_mask_and_smart_tools() -> None:
    """Availability should follow image, active-mask, and SAM readiness independently."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, _applied = _controller(document, image_id=image_id)

    project_authored_input_tool_context(controller, document)
    states = {item.tool_id: item for item in controller.palette.snapshot()}
    assert states[InputCanvasToolId.PAN_ZOOM].enabled is True
    assert states[InputCanvasToolId.SELECT_RECTANGLE].enabled is True
    assert states[InputCanvasToolId.SELECT_ELLIPSE].enabled is True
    assert states[InputCanvasToolId.SELECT_LASSO].enabled is True
    assert states[InputCanvasToolId.MOVE].enabled is False
    assert states[InputCanvasToolId.BRUSH].enabled is False
    assert states[InputCanvasToolId.ERASER].enabled is False
    assert states[InputCanvasToolId.SMART_SELECT].enabled is False
    assert states[InputCanvasToolId.SMART_MASK].enabled is False

    document.sam_ready = True
    project_authored_input_tool_context(controller, document)
    states = {item.tool_id: item for item in controller.palette.snapshot()}
    assert states[InputCanvasToolId.SMART_SELECT].enabled is True
    assert states[InputCanvasToolId.SMART_MASK].enabled is False

    document.sam_ready = False
    document.has_mask = True
    project_authored_input_tool_context(controller, document)
    states = {item.tool_id: item for item in controller.palette.snapshot()}
    assert states[InputCanvasToolId.MOVE].enabled is True
    assert states[InputCanvasToolId.MASK_RECTANGLE].enabled is True
    assert states[InputCanvasToolId.MASK_ELLIPSE].enabled is True
    assert states[InputCanvasToolId.MASK_LASSO].enabled is True
    assert states[InputCanvasToolId.BRUSH].enabled is True
    assert states[InputCanvasToolId.ERASER].enabled is True
    assert states[InputCanvasToolId.SMART_SELECT].enabled is False
    assert states[InputCanvasToolId.SMART_MASK].enabled is False

    document.sam_ready = True
    project_authored_input_tool_context(controller, document)
    smart_select = controller.palette.presentation_for(InputCanvasToolId.SMART_SELECT)
    assert smart_select is not None and smart_select.enabled
    smart_mask = controller.palette.presentation_for(InputCanvasToolId.SMART_MASK)
    assert smart_mask is not None and smart_mask.enabled


def test_input_controller_rejects_disabled_unknown_and_failed_native_modes() -> None:
    """A click must not leave a pressed button when native activation is rejected."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, applied = _controller(document, image_id=image_id, accepted=False)
    project_authored_input_tool_context(controller, document)

    assert controller.request_tool(InputCanvasToolId.BRUSH) is False
    assert controller.request_tool("not-registered") is False
    assert controller.request_tool(InputCanvasToolId.PAN_ZOOM) is False
    assert applied == [CuteCanvas.CONTROL_MODE_PANZOOM]
    assert controller.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM


def test_input_controller_synchronizes_external_native_mode_changes() -> None:
    """CuteCanvas fallback or keyboard changes must remain authoritative."""

    image_id = uuid4()
    document = _ToolDocument(has_mask=True, sam_ready=True)
    controller, _applied = _controller(document, image_id=image_id)
    project_authored_input_tool_context(controller, document)

    controller.synchronize_native_tool(CuteCanvas.CONTROL_MODE_DRAW_BRUSH)
    assert controller.palette.active_tool_id == InputCanvasToolId.BRUSH

    controller.synchronize_native_tool(CuteCanvas.CONTROL_MODE_ERASER)
    assert controller.palette.active_tool_id == InputCanvasToolId.ERASER

    document.has_mask = False
    project_authored_input_tool_context(controller, document)
    assert controller.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM


def test_input_controller_restores_held_tool_after_transient_mask_loss() -> None:
    """Owning-image switches should not replace the user's held mask tool."""

    image_id = uuid4()
    document = _ToolDocument(has_mask=True)
    controller, applied = _controller(document, image_id=image_id)
    project_authored_input_tool_context(controller, document)
    assert controller.request_tool(InputCanvasToolId.MOVE)

    document.has_mask = False
    project_authored_input_tool_context(controller, document)
    assert controller.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM

    document.has_mask = True
    project_authored_input_tool_context(controller, document)

    assert controller.palette.active_tool_id == InputCanvasToolId.MOVE
    assert applied == [
        CuteCanvas.CONTROL_MODE_MOVE,
        CuteCanvas.CONTROL_MODE_PANZOOM,
        CuteCanvas.CONTROL_MODE_MOVE,
    ]


def test_runtime_native_mode_registration_uses_the_ordinary_input_route() -> None:
    """A later editor mode should become usable without changing toolbar code."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, applied = _controller(document, image_id=image_id)
    project_authored_input_tool_context(controller, document)
    controller.tool_registry.register(
        CanvasToolContribution(
            tool_id="extension.workflow-tool",
            label=app_text("Extension workflow tool"),
            icon=QIcon(),
            kind=CanvasToolKind.MODE,
            section="workflow",
            order=650,
            required_context_tags=INPUT_CANVAS_CONTEXT_TAGS,
            required_capabilities=frozenset({INPUT_IMAGE_CAPABILITY}),
            document_operation_id="native.extension",
        )
    )

    assert controller.request_tool("extension.workflow-tool") is True
    assert applied == ["native.extension"]
    assert controller.palette.active_tool_id == "extension.workflow-tool"


def test_runtime_workflow_action_executes_without_changing_native_mode() -> None:
    """A later Comfy-backed action should not masquerade as a CuteCanvas mode."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, applied = _controller(document, image_id=image_id)
    project_authored_input_tool_context(controller, document)
    actions: list[str] = []

    def execute() -> bool:
        """Record one successful workflow-backed action."""

        actions.append("ran")
        return True

    controller.runtime.register_action(
        CanvasToolContribution(
            tool_id="workflow.remove-background",
            label=app_text("Remove background"),
            icon=QIcon(),
            kind=CanvasToolKind.ACTION,
            section="workflow",
            order=650,
            required_context_tags=INPUT_CANVAS_CONTEXT_TAGS,
            required_capabilities=frozenset({INPUT_IMAGE_CAPABILITY}),
        ),
        execute,
    )

    assert controller.request_tool("workflow.remove-background") is True
    assert actions == ["ran"]
    assert applied == []
    assert controller.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM
