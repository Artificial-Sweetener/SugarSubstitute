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

"""Coordinate exclusive whole-layer coverage editing over the Input canvas."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import LayerEdgeModificationResult, LayerEdgeOperation

from substitute.shared.logging.logger import get_logger, log_warning
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
)

from .input_canvas_tool_chrome import InputCanvasToolChrome
from .input_layer_control import InputLayerControl
from .input_layer_coverage_edit_session import InputLayerCoverageEditSession
from .input_layer_coverage_editor import InputLayerCoverageEditor
from .input_tool_options_contracts import InputToolOptionsDocumentPort

_LOGGER = get_logger("presentation.canvas.input.input_layer_coverage_edit_mode")
_CANVAS_INSET = 8
_BLOCKED_INPUT_EVENTS = frozenset(
    {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.MouseMove,
        QEvent.Type.Wheel,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.ShortcutOverride,
        QEvent.Type.ContextMenu,
        QEvent.Type.TabletPress,
        QEvent.Type.TabletMove,
        QEvent.Type.TabletRelease,
        QEvent.Type.TouchBegin,
        QEvent.Type.TouchUpdate,
        QEvent.Type.TouchEnd,
        QEvent.Type.NativeGesture,
        QEvent.Type.DragEnter,
        QEvent.Type.DragMove,
        QEvent.Type.Drop,
    }
)


class InputLayerCoverageEditMode(QObject):
    """Own exclusive chrome, input gating, target identity, and preview settlement."""

    def __init__(
        self,
        *,
        document: InputToolOptionsDocumentPort,
        input_root: QWidget,
        canvas: QWidget,
        tool_chrome: InputCanvasToolChrome,
        layer_control: InputLayerControl,
        contextual_toolbar: CanvasContextualToolbar,
        parent: QObject,
    ) -> None:
        """Bind the editor without taking ownership of durable layer content."""
        super().__init__(parent)
        self._document = document
        self._input_root = input_root
        self._canvas = canvas
        self._tool_chrome = tool_chrome
        self._layer_control = layer_control
        self._contextual_toolbar = contextual_toolbar
        self._mask_id: UUID | None = None
        self._filter_installed = False
        self._session = InputLayerCoverageEditSession(document, self)
        self.editor = InputLayerCoverageEditor(canvas)
        self.editor.previewRequested.connect(self._preview)
        self.editor.applyRequested.connect(self.apply)
        self.editor.cancelRequested.connect(self.cancel)
        self._session.finished.connect(self._completed)
        document.toolContextChanged.connect(self._synchronize_target)

    @property
    def active(self) -> bool:
        """Return whether this mode exclusively owns Input canvas interaction."""
        return self._mask_id is not None

    def begin(self, mask_id: object) -> bool:
        """Capture one selected mask and enter the exclusive preview surface."""
        if not isinstance(mask_id, UUID) or self.active:
            return False
        if not any(layer.mask_id == mask_id for layer in self._document.mask_layers()):
            return False
        if (
            self._document.active_mask_id() != mask_id
            and not self._document.set_active_mask_id(mask_id)
        ):
            return False
        if not self._session.begin(mask_id):
            return False
        self._mask_id = mask_id
        self._tool_chrome.set_suppressed(True)
        self._layer_control.set_suppressed(True)
        self._contextual_toolbar.set_suppressed(True)
        self.editor.prepare()
        self.position_editor()
        self.editor.show()
        self.editor.raise_()
        self.editor.setFocus()
        self._install_filter()
        self.editor.request_current_preview()
        return self.active

    def apply(self) -> bool:
        """Request the sole durable commit and remain exclusive until it finishes."""
        if not self.active:
            return False
        self.editor.set_applying(True)
        if self._session.apply():
            return True
        self.editor.set_applying(False)
        self.cancel()
        return False

    def cancel(self) -> bool:
        """Discard transient coverage and restore the normal editor controls."""
        was_active = self.active
        self._session.cancel()
        self._finish_mode()
        return was_active

    def position_editor(self) -> None:
        """Center the exclusive control along the Input canvas bottom edge."""
        self.editor.adjustSize()
        self.editor.move(
            max(_CANVAS_INSET, (self._canvas.width() - self.editor.width()) // 2),
            max(
                _CANVAS_INSET,
                self._canvas.height() - self.editor.height() - _CANVAS_INSET,
            ),
        )
        if self.active:
            self.editor.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Consume Input canvas interaction outside the exclusive editor subtree."""
        if (
            self.active
            and event.type() in _BLOCKED_INPUT_EVENTS
            and isinstance(watched, QWidget)
            and _descends_from(watched, self._input_root)
            and not _descends_from(watched, self.editor)
        ):
            event.accept()
            return True
        return False

    def _preview(self, operation: object, amount: int) -> None:
        """Replace the transient product from the session's immutable base."""
        if not isinstance(operation, LayerEdgeOperation):
            return
        if not self._session.preview(operation, float(amount)):
            self._finish_mode()

    def _completed(self, result: object) -> None:
        """Restore editor access after this session's sole terminal result."""
        if not isinstance(result, LayerEdgeModificationResult):
            return
        if not result.succeeded:
            log_warning(
                _LOGGER,
                "Layer coverage edit did not commit",
                mask_id=str(self._mask_id),
                layer_id=str(result.layer_id),
                operation=result.operation.value,
                reason=result.message,
            )
        self._finish_mode()

    def _synchronize_target(self, *_args: object) -> None:
        """Keep the captured mask selected or cancel if its layer disappears."""
        mask_id = self._mask_id
        if mask_id is None:
            return
        if not any(layer.mask_id == mask_id for layer in self._document.mask_layers()):
            self.cancel()
            return
        if self._document.active_mask_id() != mask_id:
            self._document.set_active_mask_id(mask_id)

    def _finish_mode(self) -> None:
        """Release input capture and restore normal canvas chrome exactly once."""
        self._mask_id = None
        self._remove_filter()
        self.editor.hide()
        self.editor.set_applying(False)
        self._tool_chrome.set_suppressed(False)
        self._layer_control.set_suppressed(False)
        self._contextual_toolbar.set_suppressed(False)

    def _install_filter(self) -> None:
        """Install one process filter for the active exclusive lifetime."""
        if self._filter_installed:
            return
        application = QApplication.instance()
        if application is None:
            return
        application.installEventFilter(self)
        self._filter_installed = True

    def _remove_filter(self) -> None:
        """Release process input observation idempotently."""
        if not self._filter_installed:
            return
        application = QApplication.instance()
        if application is not None:
            application.removeEventFilter(self)
        self._filter_installed = False


def _descends_from(widget: QWidget, ancestor: QWidget) -> bool:
    """Return whether one widget belongs to an inclusive Qt parent subtree."""
    current: QWidget | None = widget
    while current is not None:
        if current is ancestor:
            return True
        current = current.parentWidget()
    return False


__all__ = ["InputLayerCoverageEditMode"]
