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

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas

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

from .input_selection_contextual_toolbar import (
    InputSelectionContextualToolbarPage,
)
from .input_edit_session_controller import InputEditSessionController
from .input_edit_session_toolbar_controller import (
    InputEditSessionToolbarController,
)
from .input_contextual_toolbar_gestures import (
    InputContextualToolbarGestureKind,
    InputContextualToolbarGestureObserver,
    InputContextualToolbarGestureUpdate,
)
from .input_contextual_toolbar_placement import InputContextualToolbarPlacement
from .input_selection_modification_controller import (
    InputSelectionModificationController,
)
from .input_tool_options_contracts import InputToolOptionsDocumentPort
from .input_transform_session_controller import InputTransformSessionController

_SELECTION_CONTENT_ID = "input.contextual.selection"
_SELECTION_MODIFICATION_CONTENT_ID = "input.contextual.selection.modification"


class InputContextualToolbarController(QObject):
    """Route authoritative Input context into focused toolbar page owners."""

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        toolbar: CanvasContextualToolbar,
        tool_chrome: InputCanvasToolChrome,
        edit_sessions: InputEditSessionController,
        selection_authoring: InputSelectionAuthoringObserver,
        request_tool: Callable[[str], object],
        parent: QObject,
    ) -> None:
        """Bind authoritative document signals and normal chrome collaborators."""
        super().__init__(parent)
        self._document = document
        self._toolbar = toolbar
        self._edit_sessions = edit_sessions
        self._request_tool = request_tool
        self._runtime: CanvasToolRuntime | None = None
        self._gesture_active = False
        self._placement = InputContextualToolbarPlacement(
            document=document,
            toolbar=toolbar,
        )
        self._transform = InputTransformSessionController(
            document=document,
            toolbar=toolbar,
            tool_chrome=tool_chrome,
            edit_sessions=edit_sessions,
            placement=self._placement,
            parent=self,
        )
        self._session_toolbar = InputEditSessionToolbarController(
            document=document,
            toolbar=toolbar,
            edit_sessions=edit_sessions,
            placement=self._placement,
            parent=self,
        )

        document.pixelSelectionChanged.connect(self._selection_changed)
        document.canvasOperationChanged.connect(self.synchronize)
        document.canvasViewChanged.connect(self._view_changed)
        document.editorContextChanged.connect(self.synchronize)
        self._selection_modification = InputSelectionModificationController(
            document=document,
            tool_chrome=tool_chrome,
            parent=self,
        )
        self._selection_modification.changed.connect(self.synchronize)
        edit_sessions.changed.connect(self.synchronize)
        self._gestures = InputContextualToolbarGestureObserver(
            document=document,
            selection_authoring=selection_authoring,
            parent=self,
        )
        self._gestures.changed.connect(self._gesture_changed)

    @property
    def transform_active(self) -> bool:
        """Return whether the toolbar owns an explicit transform transaction."""

        return self._transform.active

    @property
    def selection_modification_active(self) -> bool:
        """Return whether the toolbar owns a reversible selection preview."""

        return self._selection_modification.active

    def bind_runtime(self, runtime: CanvasToolRuntime) -> None:
        """Bind the shared contribution runtime used by selection content."""
        self._runtime = runtime
        self._session_toolbar.bind_runtime(runtime)
        self._placement.update_selection(ContextualToolbarPlacementUpdate.RESET)
        self.synchronize()

    def bind_operation_restoration(
        self,
        restore_operation: Callable[[str], bool],
    ) -> None:
        """Bind native tool restoration through the authoritative activation owner."""

        self._transform.bind_operation_restoration(restore_operation)
        self._session_toolbar.bind_operation_restoration(restore_operation)

    def synchronize(self, *_args: object) -> None:
        """Resolve toolbar visibility and page from authoritative editor state."""
        session = self._edit_sessions.snapshot
        operation = self._document.current_canvas_operation()
        if self._gesture_active or (session is not None and session.gesture_active):
            self._toolbar.set_suppressed(True)
            return
        if self.selection_modification_active:
            self._toolbar.set_suppressed(False)
            self._show_selection_modification_page()
            return
        if self._session_toolbar.can_present(operation, session):
            self._toolbar.set_suppressed(False)
            self._session_toolbar.present(operation, session)
            return
        self._session_toolbar.observe_inactive_operation(operation)
        if (
            operation == CuteCanvas.CONTROL_MODE_TRANSFORM
            and self._transform.target is not None
        ):
            self._transform.present()
            return
        if not self._document.has_pixel_selection():
            self._transform.leave(cancel_unresolved=True)
            self._toolbar.clear_content()
            return
        self._toolbar.set_suppressed(False)
        if self._transform.active:
            self._transform.leave(cancel_unresolved=True)
        self._transform.remember_previous_operation(operation)
        self._show_selection_page()

    def apply_transform(self) -> bool:
        """Resolve transformed pixels once and restore the previous tool."""

        return self._transform.apply()

    def cancel_transform(self) -> bool:
        """Discard transformed pixels and restore the previous tool."""

        return self._transform.cancel()

    def cancel_active_transform(self) -> bool:
        """Cancel a live transform when the canvas becomes unavailable."""

        return self._transform.cancel()

    def cancel_active_edit(self) -> bool:
        """Cancel any unresolved CuteCanvas session before Input invalidation."""

        if self._transform.active:
            return self._transform.cancel()
        return self._session_toolbar.cancel()

    def begin_selection_modification(self) -> bool:
        """Capture selection state and replace normal toolbar content with its editor."""

        return self._selection_modification.begin()

    def apply_selection_modification(self) -> bool:
        """Commit the current latest preview once and restore normal toolbar content."""

        return self._selection_modification.apply()

    def cancel_selection_modification(self) -> bool:
        """Restore the captured selection and return to normal toolbar content."""

        return self._selection_modification.cancel()

    def close(self) -> None:
        """Cancel unresolved pixels and release visible contextual state."""
        self._selection_modification.close()
        if self._transform.active:
            self._transform.cancel()
        else:
            self._session_toolbar.close()
        self._transform.leave(cancel_unresolved=False)
        self._toolbar.clear_content()

    def refresh_placement(self) -> None:
        """Reproject the active contextual owner's placement after host resize."""

        self._view_changed()

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
            self._selection_modification.create_page,
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

    def _request_contextual_tool(self, tool_id: str) -> None:
        """Forward one contributed action or mode through the normal runtime path."""
        self._request_tool(tool_id)

    def _selection_changed(self, *_args: object) -> None:
        """Classify durable and preview selection geometry changes."""

        if self._gesture_active:
            return
        if self._session_toolbar.presenting:
            self._session_toolbar.refresh_placement()
            self.synchronize()
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

        if self._transform.active:
            self._transform.refresh_placement()
        elif self._session_toolbar.presenting:
            self._session_toolbar.refresh_placement()
        else:
            self._placement.update_selection(ContextualToolbarPlacementUpdate.VIEW)

    def _gesture_changed(self, value: object) -> None:
        """Apply authoritative gesture suppression before publishing settlement."""

        if not isinstance(value, InputContextualToolbarGestureUpdate):
            return
        self._gesture_active = value.active
        if value.kind is InputContextualToolbarGestureKind.TRANSFORM:
            self._transform.handle_transform_gesture(value)
        elif value.kind is InputContextualToolbarGestureKind.FLOATING_PIXELS:
            self._transform.handle_floating_gesture(value)
        elif value.settled and self._session_toolbar.presenting:
            self._session_toolbar.refresh_placement()
        elif value.settled:
            self._placement.update_selection(ContextualToolbarPlacementUpdate.RESET)
        self._toolbar.set_suppressed(value.active)
        if not value.active:
            self.synchronize()


__all__ = ["InputContextualToolbarController"]
