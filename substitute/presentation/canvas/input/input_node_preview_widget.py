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
from PySide6.QtCore import QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from .input_preview_binding import InputPreviewBinding


class InputNodePreviewWidget(QWidget):
    """Render one live document source as presentation-only picker content."""

    def __init__(
        self,
        binding: InputPreviewBinding,
        parent: QWidget | None = None,
        *,
        preferred_width: int = 352,
    ) -> None:
        """Mount an independently identified view over a shared document runtime."""
        super().__init__(parent)
        if preferred_width <= 0:
            raise ValueError("preferred_width must be positive")
        self._binding = binding
        self._preferred_width = preferred_width
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(self.sizeHint())

    @property
    def binding(self) -> InputPreviewBinding:
        """Return the immutable source mounted by this widget."""
        return self._binding

    @property
    def canvas(self) -> CuteCanvas:
        """Return the public CuteCanvas child for semantic harness inspection."""
        return self._canvas

    def sizeHint(self) -> QSize:
        """Return the picker width with the authoritative source aspect ratio."""
        return QSize(
            self._preferred_width,
            self.heightForWidth(self._preferred_width),
        )

    def hasHeightForWidth(self) -> bool:
        """Declare aspect-preserving height negotiation to the parent layout."""
        return True

    def heightForWidth(self, width: int) -> int:
        """Return the source-aspect height for one available preview width."""
        source_size = self._binding.source_size
        return max(1, round(width * source_size.height() / source_size.width()))

    def set_thumbnail_corner_radius(self, radius: int) -> None:
        """Delegate node-card chrome clipping to the authoritative viewport draw."""
        self._canvas.setViewportCornerRadius(float(radius))

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release only this viewport while preserving the shared runtime."""
        self._canvas.close()
        super().closeEvent(event)


__all__ = ["InputNodePreviewWidget"]
