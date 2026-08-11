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

"""Own reversible Input pixel-selection modification preview settlement."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget
from cutecanvas import CuteCanvas, LayerEdgeOperation, PixelSelectionModificationResult

from substitute.presentation.canvas.input.input_canvas_tool_chrome import (
    InputCanvasToolChrome,
)
from substitute.shared.logging.logger import get_logger, log_warning

from .input_selection_modification_contextual_toolbar import (
    InputSelectionModificationContextualToolbarPage,
)
from .input_tool_options_contracts import InputToolOptionsDocumentPort

_LOGGER = get_logger(
    "presentation.canvas.input.input_selection_modification_controller"
)


class InputSelectionModificationController(QObject):
    """Coordinate one asynchronous selection-edge preview and its chrome."""

    changed = Signal()

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        tool_chrome: InputCanvasToolChrome,
        parent: QObject,
    ) -> None:
        """Bind preview commands, completion, and exclusive chrome ownership."""

        super().__init__(parent)
        self._document = document
        self._tool_chrome = tool_chrome
        self._session_id: UUID | None = None
        self._request_id: UUID | None = None
        self._previous_operation: str | None = None
        self._page: InputSelectionModificationContextualToolbarPage | None = None
        document.selectionModificationCompleted.connect(self._completed)

    @property
    def active(self) -> bool:
        """Return whether one reversible selection preview remains unresolved."""

        return self._session_id is not None

    def begin(self) -> bool:
        """Capture selection state and acquire exclusive navigation input."""

        if self.active or not self._document.has_pixel_selection():
            return False
        session_id = self._document.begin_pixel_selection_modification_preview()
        if session_id is None:
            log_warning(_LOGGER, "Pixel-selection modification preview could not begin")
            return False
        previous_operation = self._document.current_canvas_operation()
        self._session_id = session_id
        self._previous_operation = previous_operation
        self._tool_chrome.set_suppressed(True)
        if (
            previous_operation != CuteCanvas.CONTROL_MODE_PANZOOM
            and not self._document.set_canvas_operation(CuteCanvas.CONTROL_MODE_PANZOOM)
        ):
            self._leave(cancel_preview=True)
            log_warning(
                _LOGGER,
                "Pixel-selection modification could not acquire canvas input",
                operation_id=previous_operation,
            )
            return False
        self.changed.emit()
        return True

    def create_page(
        self,
        parent: QWidget,
    ) -> InputSelectionModificationContextualToolbarPage:
        """Create and connect one preview editor page."""

        page = InputSelectionModificationContextualToolbarPage(parent)
        self._page = page
        page.destroyed.connect(lambda _object=None: self._release_page(page))
        page.previewRequested.connect(self._preview)
        page.applyRequested.connect(self.apply)
        page.cancelRequested.connect(self.cancel)
        page.request_initial_preview()
        return page

    def apply(self) -> bool:
        """Commit the current latest preview once."""

        session_id = self._session_id
        if session_id is None:
            return False
        page = self._page
        if page is not None:
            page.set_settlement_enabled(False)
        accepted = self._document.settle_pixel_selection_modification_preview(
            session_id
        )
        if not accepted:
            if page is not None:
                page.set_settlement_enabled(True)
            log_warning(_LOGGER, "Pixel-selection modification could not be applied")
        return accepted

    def cancel(self) -> bool:
        """Restore the captured selection and release exclusive input."""

        return self._leave(cancel_preview=True)

    def close(self) -> None:
        """Cancel any unresolved preview before owner teardown."""

        self._leave(cancel_preview=True)

    def _preview(self, operation: object, pixels: int) -> None:
        """Replace the current preview from the immutable session original."""

        session_id = self._session_id
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
        self._request_id = request_id

    def _completed(self, result: object) -> None:
        """Resolve the current preview after its asynchronous terminal result."""

        if (
            not isinstance(result, PixelSelectionModificationResult)
            or result.request_id != self._request_id
        ):
            return
        if not result.succeeded:
            log_warning(
                _LOGGER,
                "Pixel-selection modification preview failed",
                reason=result.message,
                request_id=result.request_id,
            )
        self._leave(cancel_preview=False)

    def _leave(self, *, cancel_preview: bool) -> bool:
        """Release preview state and restore its captured canvas operation."""

        session_id = self._session_id
        if session_id is None:
            return False
        previous_operation = self._previous_operation
        self._session_id = None
        self._request_id = None
        self._previous_operation = None
        accepted = (
            self._document.cancel_pixel_selection_modification_preview(session_id)
            if cancel_preview
            else True
        )
        self._tool_chrome.set_suppressed(False)
        if previous_operation is not None:
            self._restore_operation(previous_operation)
        self.changed.emit()
        return accepted

    def _restore_operation(self, operation: str) -> bool:
        """Restore captured input with a safe navigation fallback."""

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
            "Selection modification could not restore the prior canvas operation",
            operation_id=operation,
        )
        return False

    def _release_page(
        self,
        page: InputSelectionModificationContextualToolbarPage,
    ) -> None:
        """Forget only the exact page released by the toolbar host."""

        if self._page is page:
            self._page = None


__all__ = ["InputSelectionModificationController"]
