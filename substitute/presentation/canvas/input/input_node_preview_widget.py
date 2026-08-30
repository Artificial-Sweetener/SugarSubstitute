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
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from .input_preview_binding import InputPreviewBinding


class _ThumbnailCuteCanvas(CuteCanvas):
    """Allow a fit-only renderer to contract below editing-safe dimensions."""

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Return the smallest paintable viewport for thumbnail presentation."""

        return QSize(1, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Refit locked thumbnail content to the newly committed viewport size."""

        super().resizeEvent(event)
        spec = self.viewportSpec()
        if spec is None or spec.interaction is not CanvasViewportInteraction.FIT_ONLY:
            return
        self.setPanZoomLocked(False)
        self.setZoomFit()
        self.setPanZoomLocked(True)


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
        self._canvas = _ThumbnailCuteCanvas(
            document=binding.document,
            document_runtime=binding.runtime,
            features=binding.features,
        )
        binding.view_lifetime.register(self._canvas)
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

    def aspect_fit_size(
        self,
        *,
        maximum_width: int,
        maximum_height: int | None = None,
    ) -> QSize:
        """Fit the source aspect inside one optional bounding rectangle."""

        if maximum_width <= 0:
            raise ValueError("maximum_width must be positive")
        if maximum_height is not None and maximum_height <= 0:
            raise ValueError("maximum_height must be positive when supplied")
        width = maximum_width
        height = self.heightForWidth(width)
        if maximum_height is not None and height > maximum_height:
            source_size = self._binding.source_size
            width = max(
                1,
                round(maximum_height * source_size.width() / source_size.height()),
            )
            height = self.heightForWidth(width)
        return QSize(width, height)

    def set_preferred_width(self, preferred_width: int) -> None:
        """Resize this viewport while preserving its authoritative source aspect."""

        if preferred_width <= 0:
            raise ValueError("preferred_width must be positive")
        self._preferred_width = preferred_width
        self.setFixedSize(self.sizeHint())
        self.updateGeometry()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release only this viewport while preserving the shared runtime."""
        self._canvas.close()
        super().closeEvent(event)


__all__ = ["InputNodePreviewWidget"]
