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

"""Own contextual affine edit presentation and explicit settlement."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas, EditorTransformCommand, EditorTransformTarget

from substitute.presentation.canvas.input.input_canvas_tool_chrome import (
    InputCanvasToolChrome,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPlacementUpdate,
)
from substitute.shared.logging.logger import get_logger, log_warning

from .input_contextual_toolbar_gestures import InputContextualToolbarGestureUpdate
from .input_contextual_toolbar_placement import InputContextualToolbarPlacement
from .input_edit_session_controller import InputEditSessionController
from .input_tool_options_contracts import InputToolOptionsDocumentPort
from .input_transform_contextual_toolbar import InputTransformContextualToolbarPage

_LOGGER = get_logger("presentation.canvas.input.input_transform_session_controller")
_TRANSFORM_CONTENT_ID = "input.contextual.selection.transform"


class InputTransformSessionController(QObject):
    """Own one affine contextual page, gesture frame, and settlement lifecycle."""

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        toolbar: CanvasContextualToolbar,
        tool_chrome: InputCanvasToolChrome,
        edit_sessions: InputEditSessionController,
        placement: InputContextualToolbarPlacement,
        parent: QObject,
    ) -> None:
        """Bind affine commands to their document and shared chrome owners."""

        super().__init__(parent)
        self._document = document
        self._toolbar = toolbar
        self._tool_chrome = tool_chrome
        self._edit_sessions = edit_sessions
        self._placement = placement
        self._active = False
        self._target: EditorTransformTarget | None = None
        self._previous_operation = document.current_canvas_operation()
        self._restore_operation: Callable[[str], bool] = document.set_canvas_operation

    @property
    def active(self) -> bool:
        """Return whether affine editing exclusively owns normal Input chrome."""

        return self._active

    @property
    def target(self) -> EditorTransformTarget | None:
        """Return the exact affine target observed from CuteCanvas."""

        return self._target

    def bind_operation_restoration(
        self,
        restore_operation: Callable[[str], bool],
    ) -> None:
        """Route settlement restoration through authoritative tool activation."""

        self._restore_operation = restore_operation

    def can_present(self, operation: str) -> bool:
        """Return whether current public state declares an affine context."""

        return (
            operation == CuteCanvas.CONTROL_MODE_TRANSFORM and self._target is not None
        )

    def present(self) -> None:
        """Mount or refresh the affine page against its live transform frame."""

        target = self._target
        if target is None:
            return
        self._enter()
        self._toolbar.set_suppressed(False)
        self._placement.update_transform(
            target,
            ContextualToolbarPlacementUpdate.COMMAND,
        )
        page = self._toolbar.set_content(
            _TRANSFORM_CONTENT_ID,
            self._create_page,
        )
        if isinstance(page, InputTransformContextualToolbarPage):
            self._update_page(page)

    def remember_previous_operation(self, operation: str) -> None:
        """Capture the non-affine mode restored after explicit settlement."""

        self._previous_operation = operation

    def apply(self) -> bool:
        """Apply the complete provisional transform and restore its prior tool."""

        if not self._active:
            return False
        session = self._edit_sessions.snapshot
        if session is not None:
            self._edit_sessions.apply()
            accepted = session.can_apply
        else:
            accepted = self._document.apply_transform()
        if not accepted:
            log_warning(_LOGGER, "Affine transform could not be applied")
            return False
        return self._restore_previous_operation("apply")

    def cancel(self) -> bool:
        """Cancel the complete provisional transform and restore its prior tool."""

        if not self._active:
            return False
        session = self._edit_sessions.snapshot
        if session is not None:
            self._edit_sessions.cancel()
            accepted = session.can_cancel
        else:
            accepted = self._document.cancel_transform()
        if not accepted:
            log_warning(_LOGGER, "Affine transform could not be cancelled")
            return False
        return self._restore_previous_operation("cancel")

    def leave(self, *, cancel_unresolved: bool) -> None:
        """Release exclusive chrome and optionally discard suspended pixels."""

        if not self._active:
            return
        if cancel_unresolved:
            self._document.cancel_transform()
        self._active = False
        self._target = None
        self._tool_chrome.set_suppressed(False)

    def close(self) -> None:
        """Cancel unresolved affine state during Input teardown."""

        if self._active:
            self.cancel()
        self.leave(cancel_unresolved=False)

    def refresh_placement(self) -> None:
        """Follow the affine frame after viewport navigation."""

        target = self._target
        if self._active and target is not None:
            self._placement.update_transform(
                target,
                ContextualToolbarPlacementUpdate.VIEW,
            )

    def handle_transform_gesture(
        self,
        update: InputContextualToolbarGestureUpdate,
    ) -> None:
        """Track one affine phase and classify its settled frame update."""

        state = update.transform
        if state is None:
            return
        self._target = state.target
        if not update.source_active:
            self._placement.update_transform(
                state.target,
                ContextualToolbarPlacementUpdate.RESET
                if update.settled
                else ContextualToolbarPlacementUpdate.COMMAND,
            )

    def handle_floating_gesture(
        self,
        update: InputContextualToolbarGestureUpdate,
    ) -> None:
        """Track selected-pixel drag settlement from its floating frame."""

        if update.source_active:
            return
        self._placement.update_floating(
            update.floating,
            ContextualToolbarPlacementUpdate.RESET
            if update.settled
            else ContextualToolbarPlacementUpdate.COMMAND,
        )

    def _create_page(self, parent: QWidget) -> InputTransformContextualToolbarPage:
        """Create and connect one explicit affine settlement page."""

        target = self._target or EditorTransformTarget.SELECTION_CONTENT
        page = InputTransformContextualToolbarPage(target, parent)
        page.applyRequested.connect(self.apply)
        page.cancelRequested.connect(self.cancel)
        page.commandRequested.connect(self._apply_command)
        page.undoRequested.connect(self._edit_sessions.undo)
        page.redoRequested.connect(self._edit_sessions.redo)
        self._update_page(page)
        return page

    def _update_page(self, page: InputTransformContextualToolbarPage) -> None:
        """Project provisional history into the mounted affine page."""

        session = self._edit_sessions.snapshot
        page.set_session_available(
            undo=session is not None and self._edit_sessions.can_undo,
            redo=session is not None and self._edit_sessions.can_redo,
            apply=session is not None and session.can_apply,
            cancel=session.can_cancel if session is not None else True,
        )

    def _apply_command(self, command: object) -> None:
        """Route one contextual affine command through the document facade."""

        if isinstance(command, EditorTransformCommand):
            self._document.apply_transform_command(command)

    def _enter(self) -> None:
        """Suppress conflicting normal chrome on first affine presentation."""

        if self._active:
            return
        self._active = True
        self._tool_chrome.set_suppressed(True)

    def _restore_previous_operation(self, action: str) -> bool:
        """Restore the captured non-affine operation after settlement."""

        operation = self._previous_operation
        if operation == CuteCanvas.CONTROL_MODE_TRANSFORM:
            operation = CuteCanvas.CONTROL_MODE_PANZOOM
        if self._restore_operation(operation):
            return True
        if operation != CuteCanvas.CONTROL_MODE_PANZOOM and self._restore_operation(
            CuteCanvas.CONTROL_MODE_PANZOOM
        ):
            return True
        log_warning(
            _LOGGER,
            "Contextual Toolbar could not restore the prior canvas operation",
            action=action,
            operation_id=operation,
        )
        return False


__all__ = ["InputTransformSessionController"]
