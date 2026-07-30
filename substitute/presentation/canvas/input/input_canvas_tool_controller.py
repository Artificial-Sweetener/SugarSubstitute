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

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    ACTIVE_MASK_CAPABILITY,
    INPUT_CANVAS_CONTEXT_TAGS,
    INPUT_IMAGE_CAPABILITY,
    SMART_SELECT_CAPABILITY,
    InputCanvasToolId,
)
from substitute.presentation.canvas.tools import (
    CanvasToolContext,
    CanvasToolKind,
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

    def smart_select_ready(self) -> bool:
        """Return whether Smart Select can execute now."""

    def current_canvas_operation(self) -> str | None:
        """Return the current CuteCanvas document operation identity."""


class InputCanvasToolController:
    """Keep the runtime palette synchronized with authoritative canvas state."""

    def __init__(
        self,
        *,
        input_document: InputCanvasToolDocumentPort,
        operation_setter: Callable[[str], bool],
        current_image_id_provider: Callable[[], UUID | None],
        runtime: CanvasToolRuntime,
    ) -> None:
        """Store document ports and initialize a context-free palette."""

        self._input_document = input_document
        self._operation_setter = operation_setter
        self._current_image_id_provider = current_image_id_provider
        self._runtime = runtime

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
        if self._input_document.smart_select_ready():
            capabilities.add(SMART_SELECT_CAPABILITY)
        self.palette.set_context(
            CanvasToolContext(
                tags=INPUT_CANVAS_CONTEXT_TAGS,
                capabilities=frozenset(capabilities),
            )
        )
        self._synchronize_or_recover()

    def request_tool(self, tool_id: str) -> bool:
        """Activate one enabled registered mode and restore truth on rejection."""

        presentation = self.palette.presentation_for(tool_id)
        if presentation is None or not presentation.enabled:
            return False
        if presentation.kind is CanvasToolKind.ACTION:
            return self._runtime.dispatch_action(tool_id)
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
        return accepted and self.palette.active_tool_id == tool_id

    def synchronize_native_tool(self, operation_id: str) -> None:
        """Project an externally changed CuteCanvas operation into the palette."""

        tool_id = self._tool_id_for_operation(operation_id)
        if tool_id is None or not self.palette.set_active_tool(tool_id):
            self._recover_navigation_mode()

    def request_brush_after_mask_activation(self) -> bool:
        """Select Brush through the same authorization path as a toolbar click."""

        self.refresh_tool_context()
        return self.request_tool(InputCanvasToolId.BRUSH)

    def _synchronize_or_recover(self) -> None:
        """Synchronize the native mode or recover to enabled navigation."""

        operation_id = self._input_document.current_canvas_operation()
        tool_id = (
            None if operation_id is None else self._tool_id_for_operation(operation_id)
        )
        if tool_id is not None and self.palette.set_active_tool(tool_id):
            return
        self._recover_navigation_mode()

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

        return next(
            (
                presentation.tool_id
                for presentation in self.palette.snapshot()
                if presentation.document_operation_id == operation_id
            ),
            None,
        )


__all__ = ["InputCanvasToolController", "InputCanvasToolDocumentPort"]
