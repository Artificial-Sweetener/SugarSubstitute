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
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    INPUT_IMAGE_CAPABILITY,
    INPUT_CANVAS_CONTEXT_TAGS,
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.tools.model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
)


@dataclass
class _ToolDocument:
    """Expose mutable Input tool context to the controller."""

    has_mask: bool = False
    sam_ready: bool = False
    current_tool_id: str | None = InputCanvasToolId.PAN_ZOOM

    def active_image_has_mask_target(self, _image_id: UUID | None) -> bool:
        """Return current active-mask availability."""

        return self.has_mask

    def smart_select_ready(self) -> bool:
        """Return current Smart Select readiness."""

        return self.sam_ready

    def current_canvas_tool_id(self) -> str | None:
        """Return the actual CuteCanvas mode projected as a tool ID."""

        return self.current_tool_id


def _controller(
    document: _ToolDocument,
    *,
    image_id: UUID | None,
    accepted: bool = True,
) -> tuple[InputCanvasToolController, list[str]]:
    """Return one controller and its applied tool IDs."""

    runtime = create_input_canvas_tool_system()
    applied: list[str] = []

    def apply(tool_id: str) -> bool:
        """Record an accepted mode and update the fake native state."""

        applied.append(tool_id)
        if accepted:
            document.current_tool_id = tool_id
        return accepted

    return (
        InputCanvasToolController(
            input_document=document,
            control_mode_setter=apply,
            current_image_id_provider=lambda: image_id,
            runtime=runtime,
        ),
        applied,
    )


def test_input_catalog_has_expected_editor_order_and_tool_kinds() -> None:
    """The first palette should establish the durable editor ordering."""

    palette = create_input_canvas_tool_system().palette
    palette.set_context(CanvasToolContext(tags=INPUT_CANVAS_CONTEXT_TAGS))

    assert tuple(item.tool_id for item in palette.snapshot()) == (
        InputCanvasToolId.MOVE,
        InputCanvasToolId.MASK_RECTANGLE,
        InputCanvasToolId.MASK_ELLIPSE,
        InputCanvasToolId.MASK_LASSO,
        InputCanvasToolId.SMART_SELECT,
        InputCanvasToolId.BRUSH,
        InputCanvasToolId.PAN_ZOOM,
    )


def test_input_context_enables_navigation_then_mask_and_smart_tools() -> None:
    """Availability should follow image, active-mask, and SAM readiness independently."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, _applied = _controller(document, image_id=image_id)

    controller.refresh_tool_context()
    states = {item.tool_id: item for item in controller.palette.snapshot()}
    assert states[InputCanvasToolId.PAN_ZOOM].enabled is True
    assert states[InputCanvasToolId.MOVE].enabled is False
    assert states[InputCanvasToolId.BRUSH].enabled is False
    assert states[InputCanvasToolId.SMART_SELECT].enabled is False

    document.has_mask = True
    controller.refresh_tool_context()
    states = {item.tool_id: item for item in controller.palette.snapshot()}
    assert states[InputCanvasToolId.MOVE].enabled is True
    assert states[InputCanvasToolId.MASK_RECTANGLE].enabled is True
    assert states[InputCanvasToolId.MASK_ELLIPSE].enabled is True
    assert states[InputCanvasToolId.MASK_LASSO].enabled is True
    assert states[InputCanvasToolId.BRUSH].enabled is True
    assert states[InputCanvasToolId.SMART_SELECT].enabled is False

    document.sam_ready = True
    controller.refresh_tool_context()
    smart_select = controller.palette.presentation_for(InputCanvasToolId.SMART_SELECT)
    assert smart_select is not None and smart_select.enabled


def test_input_controller_rejects_disabled_unknown_and_failed_native_modes() -> None:
    """A click must not leave a pressed button when native activation is rejected."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, applied = _controller(document, image_id=image_id, accepted=False)
    controller.refresh_tool_context()

    assert controller.request_tool(InputCanvasToolId.BRUSH) is False
    assert controller.request_tool("not-registered") is False
    assert controller.request_tool(InputCanvasToolId.PAN_ZOOM) is False
    assert applied == [InputCanvasToolId.PAN_ZOOM]
    assert controller.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM


def test_input_controller_synchronizes_external_native_mode_changes() -> None:
    """CuteCanvas fallback or keyboard changes must remain authoritative."""

    image_id = uuid4()
    document = _ToolDocument(has_mask=True, sam_ready=True)
    controller, _applied = _controller(document, image_id=image_id)
    controller.refresh_tool_context()

    controller.synchronize_native_tool(InputCanvasToolId.BRUSH)
    assert controller.palette.active_tool_id == InputCanvasToolId.BRUSH

    document.has_mask = False
    controller.refresh_tool_context()
    assert controller.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM


def test_mask_activation_brush_request_uses_the_same_palette_policy() -> None:
    """Load Image as Mask activation should route through ordinary Brush selection."""

    image_id = uuid4()
    document = _ToolDocument(has_mask=True)
    controller, applied = _controller(document, image_id=image_id)
    controller.refresh_tool_context()

    assert controller.request_brush_after_mask_activation() is True
    assert applied == [InputCanvasToolId.BRUSH]
    assert controller.palette.active_tool_id == InputCanvasToolId.BRUSH


def test_runtime_native_mode_registration_uses_the_ordinary_input_route() -> None:
    """A later editor mode should become usable without changing toolbar code."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, applied = _controller(document, image_id=image_id)
    controller.refresh_tool_context()
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
        )
    )

    assert controller.request_tool("extension.workflow-tool") is True
    assert applied == ["extension.workflow-tool"]
    assert controller.palette.active_tool_id == "extension.workflow-tool"


def test_runtime_workflow_action_executes_without_changing_native_mode() -> None:
    """A later Comfy-backed action should not masquerade as a CuteCanvas mode."""

    image_id = uuid4()
    document = _ToolDocument()
    controller, applied = _controller(document, image_id=image_id)
    controller.refresh_tool_context()
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
