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

"""Coordinate Input selection state with the shared Contextual Toolbar."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from cutecanvas import (
    CuteCanvas,
    EditorTransformCommand,
    EditorTransformTarget,
    LayerEdgeOperation,
    PixelSelectionModificationResult,
)

from substitute.presentation.canvas.input.input_canvas_tool_chrome import (
    InputCanvasToolChrome,
)
from substitute.presentation.canvas.input.input_selection_authoring_observer import (
    InputSelectionAuthoringObserver,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPlacementUpdate,
)
from substitute.presentation.canvas.tools import CanvasToolRuntime
from substitute.shared.logging.logger import get_logger, log_warning

from .input_selection_contextual_toolbar import (
    InputSelectionContextualToolbarPage,
)
from .input_contextual_toolbar_gestures import (
    InputContextualToolbarGestureKind,
    InputContextualToolbarGestureObserver,
    InputContextualToolbarGestureUpdate,
)
from .input_contextual_toolbar_placement import InputContextualToolbarPlacement
from .input_selection_modification_contextual_toolbar import (
    InputSelectionModificationContextualToolbarPage,
)
from .input_tool_options_contracts import InputToolOptionsDocumentPort
from .input_transform_contextual_toolbar import (
    InputTransformContextualToolbarPage,
)

_LOGGER = get_logger("presentation.canvas.input.input_contextual_toolbar_controller")
_SELECTION_CONTENT_ID = "input.contextual.selection"
_SELECTION_MODIFICATION_CONTENT_ID = "input.contextual.selection.modification"
_TRANSFORM_CONTENT_ID = "input.contextual.selection.transform"


class InputContextualToolbarController(QObject):
    """Own Input context resolution and selected-pixel transform settlement."""

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        toolbar: CanvasContextualToolbar,
        tool_chrome: InputCanvasToolChrome,
        selection_authoring: InputSelectionAuthoringObserver,
        request_tool: Callable[[str], object],
        parent: QObject,
    ) -> None:
        """Bind authoritative document signals and normal chrome collaborators."""
        super().__init__(parent)
        self._document = document
        self._toolbar = toolbar
        self._tool_chrome = tool_chrome
        self._request_tool = request_tool
        self._runtime: CanvasToolRuntime | None = None
        self._transform_active = False
        self._gesture_active = False
        self._transform_target: EditorTransformTarget | None = None
        self._selection_modification_session_id: UUID | None = None
        self._selection_modification_request_id: UUID | None = None
        self._selection_modification_previous_operation: str | None = None
        self._last_non_transform_operation = document.current_canvas_operation()
        self._placement = InputContextualToolbarPlacement(
            document=document,
            toolbar=toolbar,
        )

        document.pixelSelectionChanged.connect(self._selection_changed)
        document.canvasOperationChanged.connect(self.synchronize)
        document.canvasViewChanged.connect(self._view_changed)
        document.editorContextChanged.connect(self.synchronize)
        document.selectionModificationCompleted.connect(
            self._selection_modification_completed
        )
        self._gestures = InputContextualToolbarGestureObserver(
            document=document,
            selection_authoring=selection_authoring,
            parent=self,
        )
        self._gestures.changed.connect(self._gesture_changed)

    @property
    def transform_active(self) -> bool:
        """Return whether the toolbar owns an explicit transform transaction."""
        return self._transform_active

    @property
    def selection_modification_active(self) -> bool:
        """Return whether the toolbar owns a reversible selection preview."""

        return self._selection_modification_session_id is not None

    def bind_runtime(self, runtime: CanvasToolRuntime) -> None:
        """Bind the shared contribution runtime used by selection content."""
        self._runtime = runtime
        self._placement.update_selection(ContextualToolbarPlacementUpdate.RESET)
        self.synchronize()

    def synchronize(self, *_args: object) -> None:
        """Resolve toolbar visibility and page from authoritative editor state."""
        if self._gesture_active:
            self._toolbar.set_suppressed(True)
            return
        if self.selection_modification_active:
            self._toolbar.set_suppressed(False)
            self._show_selection_modification_page()
            return
        operation = self._document.current_canvas_operation()
        if (
            operation == CuteCanvas.CONTROL_MODE_TRANSFORM
            and self._transform_target is not None
        ):
            self._enter_transform()
            self._placement.update_transform(
                self._transform_target,
                ContextualToolbarPlacementUpdate.COMMAND,
            )
            self._show_transform_page()
            return
        if not self._document.has_pixel_selection():
            self._leave_transform(cancel_unresolved=True)
            self._toolbar.clear_content()
            return
        self._toolbar.set_suppressed(False)
        if self._transform_active:
            self._leave_transform(cancel_unresolved=True)
        self._last_non_transform_operation = operation
        self._show_selection_page()

    def apply_transform(self) -> bool:
        """Resolve transformed pixels once and restore the previous tool."""
        if not self._transform_active:
            return False
        if not self._document.apply_transform():
            log_warning(_LOGGER, "Affine transform could not be applied")
            return False
        return self._restore_previous_operation("apply")

    def cancel_transform(self) -> bool:
        """Discard transformed pixels and restore the previous tool."""
        if not self._transform_active:
            return False
        if not self._document.cancel_transform():
            log_warning(_LOGGER, "Affine transform could not be cancelled")
            return False
        return self._restore_previous_operation("cancel")

    def cancel_active_transform(self) -> bool:
        """Cancel a live transform when the canvas becomes unavailable."""
        if not self._transform_active:
            return False
        return self.cancel_transform()

    def begin_selection_modification(self) -> bool:
        """Capture selection state and replace normal toolbar content with its editor."""

        if (
            self.selection_modification_active
            or not self._document.has_pixel_selection()
        ):
            return False
        session_id = self._document.begin_pixel_selection_modification_preview()
        if session_id is None:
            log_warning(_LOGGER, "Pixel-selection modification preview could not begin")
            return False
        previous_operation = self._document.current_canvas_operation()
        self._selection_modification_session_id = session_id
        self._selection_modification_previous_operation = previous_operation
        self._set_exclusive_chrome(True)
        if (
            previous_operation != CuteCanvas.CONTROL_MODE_PANZOOM
            and not self._document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
        ):
            self._leave_selection_modification(cancel_preview=True)
            log_warning(
                _LOGGER,
                "Pixel-selection modification could not acquire canvas input",
                operation_id=previous_operation,
            )
            return False
        self._show_selection_modification_page()
        page = self._toolbar.page
        if not isinstance(page, InputSelectionModificationContextualToolbarPage):
            self._leave_selection_modification(cancel_preview=True)
            return False
        page.request_initial_preview()
        return True

    def apply_selection_modification(self) -> bool:
        """Commit the current latest preview once and restore normal toolbar content."""

        session_id = self._selection_modification_session_id
        if session_id is None:
            return False
        page = self._toolbar.page
        if isinstance(page, InputSelectionModificationContextualToolbarPage):
            page.set_settlement_enabled(False)
        accepted = self._document.settle_pixel_selection_modification_preview(
            session_id
        )
        if not accepted:
            if isinstance(page, InputSelectionModificationContextualToolbarPage):
                page.set_settlement_enabled(True)
            log_warning(_LOGGER, "Pixel-selection modification could not be applied")
            return False
        return True

    def cancel_selection_modification(self) -> bool:
        """Restore the captured selection and return to normal toolbar content."""

        return self._leave_selection_modification(cancel_preview=True)

    def close(self) -> None:
        """Cancel unresolved pixels and release visible contextual state."""
        self._leave_selection_modification(cancel_preview=True)
        self._leave_transform(cancel_unresolved=True)
        self._toolbar.clear_content()

    def refresh_placement(self) -> None:
        """Reproject selection-relative placement after host geometry changes."""
        self._placement.update_selection(ContextualToolbarPlacementUpdate.VIEW)

    def _show_selection_page(self) -> None:
        """Mount the default selection entry and contributed actions."""
        runtime = self._runtime
        if runtime is None:
            self._toolbar.clear_content()
            return
        self._toolbar.set_content(
            _SELECTION_CONTENT_ID,
            lambda parent: self._create_selection_page(runtime, parent),
        )

    def _show_selection_modification_page(self) -> None:
        """Replace normal content with one explicit preview transaction row."""

        self._toolbar.set_content(
            _SELECTION_MODIFICATION_CONTENT_ID,
            self._create_selection_modification_page,
        )

    def _show_transform_page(self) -> None:
        """Mount explicit transform settlement in the same draggable shell."""
        self._toolbar.set_content(
            _TRANSFORM_CONTENT_ID,
            self._create_transform_page,
        )

    def _create_selection_page(
        self,
        runtime: CanvasToolRuntime,
        parent: QWidget,
    ) -> InputSelectionContextualToolbarPage:
        """Create and connect one default selection page."""
        page = InputSelectionContextualToolbarPage(
            runtime=runtime,
            parent=parent,
        )
        page.modifyRequested.connect(self.begin_selection_modification)
        page.toolRequested.connect(self._request_contextual_tool)
        return page

    def _create_selection_modification_page(
        self,
        parent: QWidget,
    ) -> InputSelectionModificationContextualToolbarPage:
        """Create and connect one reversible modification page."""

        page = InputSelectionModificationContextualToolbarPage(parent)
        page.previewRequested.connect(self._preview_selection_modification)
        page.applyRequested.connect(self.apply_selection_modification)
        page.cancelRequested.connect(self.cancel_selection_modification)
        return page

    def _create_transform_page(
        self,
        parent: QWidget,
    ) -> InputTransformContextualToolbarPage:
        """Create and connect one explicit transform settlement page."""
        target = self._transform_target
        if target is None:
            target = EditorTransformTarget.SELECTION_CONTENT
        page = InputTransformContextualToolbarPage(target, parent)
        page.applyRequested.connect(self.apply_transform)
        page.cancelRequested.connect(self.cancel_transform)
        page.commandRequested.connect(self._apply_transform_command)
        return page

    def _apply_transform_command(self, command: object) -> None:
        """Route one contextual command through the shared CuteCanvas session."""
        if isinstance(command, EditorTransformCommand):
            self._document.apply_transform_command(command)

    def _request_contextual_tool(self, tool_id: str) -> None:
        """Forward one contributed action or mode through the normal runtime path."""
        self._request_tool(tool_id)

    def _selection_changed(self, *_args: object) -> None:
        """Classify durable and preview selection geometry changes."""

        if self._gesture_active:
            return
        self._placement.update_selection(
            ContextualToolbarPlacementUpdate.COMMAND
            if self.selection_modification_active
            else ContextualToolbarPlacementUpdate.RESET,
            retain_when_missing=self.selection_modification_active,
        )
        self.synchronize()

    def _view_changed(self, *_args: object) -> None:
        """Intentionally follow projected selection bounds through navigation."""
        if self._transform_active:
            target = self._transform_target
            if target is not None:
                self._placement.update_transform(
                    target,
                    ContextualToolbarPlacementUpdate.VIEW,
                )
        else:
            self._placement.update_selection(ContextualToolbarPlacementUpdate.VIEW)

    def _gesture_changed(self, value: object) -> None:
        """Apply authoritative gesture suppression before publishing settlement."""

        if not isinstance(value, InputContextualToolbarGestureUpdate):
            return
        self._gesture_active = value.active
        if value.kind is InputContextualToolbarGestureKind.TRANSFORM:
            self._handle_transform_gesture(value)
        elif value.kind is InputContextualToolbarGestureKind.FLOATING_PIXELS:
            self._handle_floating_gesture(value)
        elif value.settled:
            self._placement.update_selection(ContextualToolbarPlacementUpdate.RESET)
        self._toolbar.set_suppressed(value.active)
        if not value.active:
            self.synchronize()

    def _handle_transform_gesture(
        self,
        update: InputContextualToolbarGestureUpdate,
    ) -> None:
        """Track one affine phase and classify its frame update."""

        state = update.transform
        if state is None:
            return
        self._transform_target = state.target
        if not update.source_active:
            self._placement.update_transform(
                state.target,
                ContextualToolbarPlacementUpdate.RESET
                if update.settled
                else ContextualToolbarPlacementUpdate.COMMAND,
            )

    def _handle_floating_gesture(
        self,
        update: InputContextualToolbarGestureUpdate,
    ) -> None:
        """Track selected-pixel drag settlement from its floating frame."""

        state = update.floating
        if update.source_active:
            return
        self._placement.update_floating(
            state,
            ContextualToolbarPlacementUpdate.RESET
            if update.settled
            else ContextualToolbarPlacementUpdate.COMMAND,
        )

    def _preview_selection_modification(
        self,
        operation: object,
        pixels: int,
    ) -> None:
        """Replace the current preview from the session's immutable original."""

        session_id = self._selection_modification_session_id
        if session_id is None or not isinstance(operation, LayerEdgeOperation):
            return
        request_id = self._document.update_pixel_selection_modification_preview(
            session_id,
            operation,
            pixels,
        )
        if request_id is None:
            log_warning(
                _LOGGER,
                "Pixel-selection modification preview could not be updated",
                operation=operation.value,
                pixels=pixels,
            )
            return
        self._selection_modification_request_id = request_id

    def _selection_modification_completed(self, result: object) -> None:
        """Leave a preview page when its current request fails asynchronously."""

        if (
            not isinstance(result, PixelSelectionModificationResult)
            or result.request_id != self._selection_modification_request_id
        ):
            return
        if not result.succeeded:
            log_warning(
                _LOGGER,
                "Pixel-selection modification preview failed",
                reason=result.message,
                request_id=result.request_id,
            )
        self._leave_selection_modification(cancel_preview=False)

    def _leave_selection_modification(self, *, cancel_preview: bool) -> bool:
        """Release preview UI and optionally restore its captured selection."""

        session_id = self._selection_modification_session_id
        if session_id is None:
            return False
        previous_operation = self._selection_modification_previous_operation
        self._selection_modification_session_id = None
        self._selection_modification_request_id = None
        self._selection_modification_previous_operation = None
        accepted = (
            self._document.cancel_pixel_selection_modification_preview(session_id)
            if cancel_preview
            else True
        )
        self._set_exclusive_chrome(False)
        if previous_operation is not None:
            self._restore_operation(previous_operation, "selection modification")
        self.synchronize()
        return accepted

    def _enter_transform(self) -> None:
        """Capture the previous tool and suppress conflicting normal chrome once."""
        if self._transform_active:
            return
        self._transform_active = True
        self._set_exclusive_chrome(True)

    def _leave_transform(self, *, cancel_unresolved: bool) -> None:
        """Release exclusive chrome and optionally discard suspended pixels."""
        if not self._transform_active:
            return
        if cancel_unresolved:
            self._document.cancel_transform()
        self._transform_active = False
        self._transform_target = None
        self._set_exclusive_chrome(False)

    def _restore_previous_operation(self, action: str) -> bool:
        """Restore the captured non-transform operation after explicit settlement."""
        return self._restore_operation(self._last_non_transform_operation, action)

    def _restore_operation(self, operation: str, action: str) -> bool:
        """Restore one captured canvas operation with a safe navigation fallback."""

        if operation == CuteCanvas.CONTROL_MODE_TRANSFORM:
            operation = CuteCanvas.CONTROL_MODE_PANZOOM
        if self._document.set_canvas_operation(operation):
            return True
        if (
            operation != CuteCanvas.CONTROL_MODE_PANZOOM
            and self._document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
        ):
            return True
        log_warning(
            _LOGGER,
            "Contextual Toolbar could not restore the prior canvas operation",
            action=action,
            operation_id=operation,
        )
        return False

    def _set_exclusive_chrome(self, suppressed: bool) -> None:
        """Apply one shared exclusivity policy to normal Input controls."""

        self._tool_chrome.set_suppressed(suppressed)


__all__ = ["InputContextualToolbarController"]
