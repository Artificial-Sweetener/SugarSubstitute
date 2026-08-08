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

"""Coordinate Input tool context and CuteCanvas mode activation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID
from cutecanvas import EditorTransformTarget
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    ACTIVE_MASK_CAPABILITY,
    INPUT_CANVAS_CONTEXT_TAGS,
    INPUT_IMAGE_CAPABILITY,
    LAYER_TRANSFORM_CAPABILITY,
    PIXEL_SELECTION_CAPABILITY,
    SELECTION_CLEAR_CAPABILITY,
    SELECTION_TRANSFORM_CAPABILITY,
    SMART_SEGMENTATION_CAPABILITY,
    InputCanvasToolId,
)
from substitute.presentation.canvas.tools import (
    CanvasToolContext,
    CanvasToolKind,
    CanvasToolLayout,
    CanvasToolPalette,
    CanvasToolRegistry,
    CanvasToolRuntime,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_canvas_tool_controller")


class InputCanvasToolDocumentPort(Protocol):
    """Expose Input document state required for contextual tool projection."""

    def active_image_has_mask_target(self, image_id: UUID | None) -> bool:
        """Return whether the active image owns the active editable mask."""

    def smart_segmentation_ready(self) -> bool:
        """Return whether Smart segmentation can execute now."""

    def has_pixel_selection(self) -> bool:
        """Return whether the active composition owns pixel selection."""

    def selection_transform_available(self) -> bool:
        """Return whether current selected pixels support affine transform."""

    def selection_clear_available(self) -> bool:
        """Return whether current selected pixels can clear their layer."""

    def layer_transform_available(self) -> bool:
        """Return whether the active layer has meaningful transform content."""

    def current_canvas_operation(self) -> str | None:
        """Return the current CuteCanvas document operation identity."""

    def activate_transform(self, target: EditorTransformTarget) -> bool:
        """Activate the shared affine mode against one explicit target."""


class InputCanvasToolController:
    """Keep the runtime palette synchronized with authoritative canvas state."""

    def __init__(
        self,
        *,
        input_document: InputCanvasToolDocumentPort,
        operation_setter: Callable[[str], bool],
        current_image_id_provider: Callable[[], UUID | None],
        runtime: CanvasToolRuntime,
        layout: CanvasToolLayout | None = None,
    ) -> None:
        """Store document ports and initialize a context-free palette."""

        self._input_document = input_document
        self._operation_setter = operation_setter
        self._current_image_id_provider = current_image_id_provider
        self._runtime = runtime
        self._layout = layout
        self._requested_native_tool_id: str | None = None
        self._held_tool_id: str | None = None

    @property
    def palette(self) -> CanvasToolPalette:
        """Return the contextual presentation owner bound to Input chrome."""

        return self._runtime.palette

    @property
    def tool_registry(self) -> CanvasToolRegistry:
        """Return the runtime extension point for additional Input tools."""

        return self._runtime.registry

    @property
    def runtime(self) -> CanvasToolRuntime:
        """Return the runtime extension owner for modes and workflow actions."""

        return self._runtime

    def refresh_tool_context(self) -> None:
        """Project current image, active mask, and Smart Select readiness."""

        image_id = self._current_image_id_provider()
        capabilities: set[str] = set()
        if image_id is not None:
            capabilities.add(INPUT_IMAGE_CAPABILITY)
        if self._input_document.active_image_has_mask_target(image_id):
            capabilities.add(ACTIVE_MASK_CAPABILITY)
            if self._input_document.layer_transform_available():
                capabilities.add(LAYER_TRANSFORM_CAPABILITY)
        if self._input_document.smart_segmentation_ready():
            capabilities.add(SMART_SEGMENTATION_CAPABILITY)
        if self._input_document.has_pixel_selection():
            capabilities.add(PIXEL_SELECTION_CAPABILITY)
            if self._input_document.selection_transform_available():
                capabilities.add(SELECTION_TRANSFORM_CAPABILITY)
            if self._input_document.selection_clear_available():
                capabilities.add(SELECTION_CLEAR_CAPABILITY)
        self.palette.set_context(
            CanvasToolContext(
                tags=INPUT_CANVAS_CONTEXT_TAGS,
                capabilities=frozenset(capabilities),
                capability_denials=(
                    (
                        LAYER_TRANSFORM_CAPABILITY,
                        app_text("Nothing to transform!"),
                    ),
                ),
            )
        )
        if self._restore_held_tool():
            return
        self._synchronize_or_recover()

    def request_tool(self, tool_id: str) -> bool:
        """Activate one enabled registered mode and restore truth on rejection."""

        presentation = self.palette.presentation_for(tool_id)
        if presentation is None or not presentation.enabled:
            return False
        if presentation.kind is CanvasToolKind.ACTION:
            return self._runtime.dispatch_action(tool_id)
        transform_target = {
            InputCanvasToolId.TRANSFORM_SELECTION: (
                EditorTransformTarget.SELECTION_CONTENT
            ),
            InputCanvasToolId.TRANSFORM_LAYER: EditorTransformTarget.LAYER_CONTENT,
        }.get(tool_id)
        if transform_target is not None:
            self._requested_native_tool_id = tool_id
            try:
                accepted = self._input_document.activate_transform(transform_target)
            finally:
                self._requested_native_tool_id = None
            if accepted:
                self.palette.set_active_tool(tool_id)
            else:
                self._synchronize_or_recover()
            activated = accepted and self.palette.active_tool_id == tool_id
            if activated:
                self._held_tool_id = tool_id
            if activated and self._layout is not None:
                self._layout.remember_tool(tool_id)
            return activated
        operation_id = presentation.document_operation_id
        if operation_id is None:
            return False
        accepted = self._operation_setter(operation_id)
        self._synchronize_or_recover()
        if not accepted:
            log_warning(
                _LOGGER,
                "Input canvas tool activation rejected",
                tool_id=tool_id,
                document_operation_id=self._input_document.current_canvas_operation(),
            )
        activated = accepted and self.palette.active_tool_id == tool_id
        if activated:
            self._held_tool_id = tool_id
        if activated and self._layout is not None:
            self._layout.remember_tool(tool_id)
        return activated

    def synchronize_native_tool(self, operation_id: str) -> None:
        """Project an externally changed CuteCanvas operation into the palette."""

        tool_id = self._tool_id_for_operation(operation_id)
        if tool_id is None or not self.palette.set_active_tool(tool_id):
            self._recover_navigation_mode()
            return
        if self._layout is not None:
            self._layout.remember_tool(tool_id)

    def _synchronize_or_recover(self) -> None:
        """Synchronize the native mode or recover to enabled navigation."""

        operation_id = self._input_document.current_canvas_operation()
        tool_id = (
            None if operation_id is None else self._tool_id_for_operation(operation_id)
        )
        if tool_id is not None and self.palette.set_active_tool(tool_id):
            return
        self._recover_navigation_mode()

    def _restore_held_tool(self) -> bool:
        """Restore a user-held mode after transient capability loss clears."""

        tool_id = self._held_tool_id
        if tool_id is None:
            return False
        presentation = self.palette.presentation_for(tool_id)
        if presentation is None or not presentation.enabled:
            return False
        return self.request_tool(tool_id)

    def _recover_navigation_mode(self) -> None:
        """Use Pan/Zoom as the safe active mode when its context is available."""

        navigation = self.palette.presentation_for(InputCanvasToolId.PAN_ZOOM)
        if navigation is None or not navigation.enabled:
            self.palette.set_active_tool(None)
            return
        operation_id = navigation.document_operation_id
        if operation_id is None:
            self.palette.set_active_tool(None)
            return
        if self._input_document.current_canvas_operation() != operation_id:
            self._operation_setter(operation_id)
        native_operation_id = self._input_document.current_canvas_operation()
        self.palette.set_active_tool(
            InputCanvasToolId.PAN_ZOOM if native_operation_id == operation_id else None
        )

    def _tool_id_for_operation(self, operation_id: str) -> str | None:
        """Resolve one document operation through current registry metadata."""

        preferred_ids = (
            self._requested_native_tool_id,
            self.palette.active_tool_id,
        )
        for tool_id in preferred_ids:
            if tool_id is None:
                continue
            presentation = self.palette.presentation_for(tool_id)
            if (
                presentation is not None
                and presentation.enabled
                and presentation.document_operation_id == operation_id
            ):
                return tool_id
        return next(
            (
                presentation.tool_id
                for presentation in self.palette.snapshot()
                if presentation.enabled
                and presentation.document_operation_id == operation_id
            ),
            None,
        )


__all__ = ["InputCanvasToolController", "InputCanvasToolDocumentPort"]
