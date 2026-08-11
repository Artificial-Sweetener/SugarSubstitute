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

"""Own contextual presentation for declared non-transform edit tools."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas, EditSessionKind, EditSessionSnapshot
from sugarsubstitute_shared.localization import ApplicationText

from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPlacementUpdate,
)
from substitute.presentation.canvas.tools import CanvasToolRuntime
from substitute.shared.logging.logger import get_logger, log_warning

from .input_contextual_toolbar_placement import InputContextualToolbarPlacement
from .input_edit_session_contextual_toolbar import (
    InputEditSessionContextualToolbarPage,
)
from .input_edit_session_controller import InputEditSessionController
from .input_tool_options_contracts import InputToolOptionsDocumentPort

_LOGGER = get_logger("presentation.canvas.input.input_edit_session_toolbar_controller")
_EDIT_SESSION_CONTENT_ID = "input.contextual.edit_session"
_ARMED_OPERATIONS = frozenset({CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE})


class InputEditSessionToolbarController(QObject):
    """Present armed and active non-transform sessions against canvas geometry."""

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        toolbar: CanvasContextualToolbar,
        edit_sessions: InputEditSessionController,
        placement: InputContextualToolbarPlacement,
        parent: QObject,
    ) -> None:
        """Bind session state, tool state, and contextual page collaborators."""

        super().__init__(parent)
        self._document = document
        self._toolbar = toolbar
        self._edit_sessions = edit_sessions
        self._placement = placement
        self._runtime: CanvasToolRuntime | None = None
        self._previous_operation = document.current_canvas_operation()
        self._restore_operation: Callable[[str], bool] = document.set_canvas_operation
        self._presenting = False

    @property
    def presenting(self) -> bool:
        """Return whether an armed or active non-transform session owns the page."""

        return self._presenting

    def bind_runtime(self, runtime: CanvasToolRuntime) -> None:
        """Bind localized tool presentation from the shared runtime."""

        self._runtime = runtime

    def bind_operation_restoration(
        self,
        restore_operation: Callable[[str], bool],
    ) -> None:
        """Route tool exit through authoritative native activation."""

        self._restore_operation = restore_operation

    def can_present(
        self,
        operation: str,
        session: EditSessionSnapshot | None,
    ) -> bool:
        """Return whether current state declares a supported contextual edit tool."""

        return (
            session is not None and session.kind is not EditSessionKind.TRANSFORM
        ) or operation in _ARMED_OPERATIONS

    def present(
        self,
        operation: str,
        session: EditSessionSnapshot | None,
    ) -> None:
        """Mount the tool page immediately and refresh public session commands."""

        first_presentation = not self._presenting
        self._presenting = True
        self._placement.update_canvas(
            ContextualToolbarPlacementUpdate.RESET
            if first_presentation
            else ContextualToolbarPlacementUpdate.COMMAND
        )
        page = self._toolbar.set_content(
            _EDIT_SESSION_CONTENT_ID,
            lambda parent: self._create_page(
                session.tool_mode if session is not None else operation,
                parent,
            ),
        )
        if isinstance(page, InputEditSessionContextualToolbarPage):
            page.set_available(
                undo=session is not None and self._edit_sessions.can_undo,
                redo=session is not None and self._edit_sessions.can_redo,
                apply=session is not None and session.can_apply,
                cancel=session is None or session.can_cancel,
            )

    def observe_inactive_operation(self, operation: str) -> None:
        """Remember the exact tool restored after the contextual edit exits."""

        if operation not in _ARMED_OPERATIONS and self._edit_sessions.snapshot is None:
            self._previous_operation = operation
            self._presenting = False

    def refresh_placement(self) -> None:
        """Follow the canvas projection after viewport navigation."""

        if self._presenting:
            self._placement.update_canvas(ContextualToolbarPlacementUpdate.VIEW)

    def apply(self) -> bool:
        """Apply the active provisional session and exit its tool."""

        session = self._edit_sessions.snapshot
        if session is None or not session.can_apply:
            return False
        self._edit_sessions.apply()
        return self._restore_previous_operation("apply")

    def cancel(self) -> bool:
        """Cancel provisional state, if any, and exit the armed tool."""

        session = self._edit_sessions.snapshot
        if session is not None:
            if not session.can_cancel:
                return False
            self._edit_sessions.cancel()
        if not self._presenting:
            return session is not None
        return self._restore_previous_operation("cancel")

    def close(self) -> None:
        """Cancel unresolved state without changing tools during teardown."""

        if self._edit_sessions.snapshot is not None:
            self._edit_sessions.cancel()
        self._presenting = False

    def _create_page(
        self,
        operation: str,
        parent: QWidget,
    ) -> InputEditSessionContextualToolbarPage:
        """Create visible history and settlement for one declared edit tool."""

        page = InputEditSessionContextualToolbarPage(
            self._runtime_label_for_operation(operation),
            parent,
        )
        page.undoRequested.connect(self._edit_sessions.undo)
        page.redoRequested.connect(self._edit_sessions.redo)
        page.applyRequested.connect(self.apply)
        page.cancelRequested.connect(self.cancel)
        return page

    def _runtime_label_for_operation(
        self,
        operation: str,
    ) -> ApplicationText | None:
        """Return localized runtime text for one native operation."""

        runtime = self._runtime
        if runtime is None:
            return None
        presentation = next(
            (
                candidate
                for candidate in runtime.palette.snapshot()
                if candidate.document_operation_id == operation
            ),
            None,
        )
        return None if presentation is None else presentation.label

    def _restore_previous_operation(self, action: str) -> bool:
        """Restore the tool active before the contextual edit was armed."""

        operation = self._previous_operation
        if operation in _ARMED_OPERATIONS:
            operation = CuteCanvas.CONTROL_MODE_PANZOOM
        if self._restore_operation(operation):
            return True
        if operation != CuteCanvas.CONTROL_MODE_PANZOOM and self._restore_operation(
            CuteCanvas.CONTROL_MODE_PANZOOM
        ):
            return True
        log_warning(
            _LOGGER,
            "Contextual edit tool could not restore the prior canvas operation",
            action=action,
            operation_id=operation,
        )
        return False


__all__ = ["InputEditSessionToolbarController"]
