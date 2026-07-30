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
"""Mount one responsive fit-only CuteCanvas node preview."""

from __future__ import annotations

import uuid

from cutecanvas import (
    CanvasViewportInteraction,
    CanvasViewportSpec,
    CuteCanvas,
)
from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .input_preview_binding import InputPreviewBinding


class InputNodePreviewWidget(QWidget):
    """Present a live document source without exposing viewport navigation."""

    clicked = Signal()

    def __init__(
        self,
        binding: InputPreviewBinding,
        parent: QWidget | None = None,
    ) -> None:
        """Mount an independently identified view over a shared document runtime."""
        super().__init__(parent)
        self._binding = binding
        self._canvas = CuteCanvas(
            document=binding.document,
            document_runtime=binding.runtime,
            features=binding.features,
        )
        self._canvas.setViewportSpec(
            CanvasViewportSpec(
                binding.source,
                viewport_id=uuid.uuid4(),
                interaction=CanvasViewportInteraction.FIT_ONLY,
                render_variant=binding.render_variant,
            )
        )
        self._canvas.installEventFilter(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self.setMinimumSize(96, 96)

    @property
    def binding(self) -> InputPreviewBinding:
        """Return the immutable source mounted by this widget."""
        return self._binding

    @property
    def canvas(self) -> CuteCanvas:
        """Return the public CuteCanvas child for semantic harness inspection."""
        return self._canvas

    def sizeHint(self) -> QSize:
        """Return a compact preview size that remains free to reflow."""
        return QSize(352, 240)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Publish left-button releases without enabling canvas navigation."""
        if (
            watched is self._canvas
            and isinstance(event, QMouseEvent)
            and event.type() is QEvent.Type.MouseButtonRelease
            and event.button() is Qt.MouseButton.LeftButton
        ):
            self.clicked.emit()
        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release only this viewport while preserving the shared runtime."""
        self._canvas.close()
        super().closeEvent(event)


__all__ = ["InputNodePreviewWidget"]
