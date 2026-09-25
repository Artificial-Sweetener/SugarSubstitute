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

"""Project paused decoded video frames into stable CuteCanvas content."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from substitute.application.ports.video import (
    VIDEO_REPRESENTATIVE_FRAME_MAX_EDGE,
    VideoRepresentativeFrame,
)
from substitute.presentation.canvas.output.output_document import (
    OutputCanvasDocument,
)


class OutputVideoRepresentativeFramePresenter:
    """Convert native BGR0 frames and replace one stable Output composition."""

    def __init__(self, document: OutputCanvasDocument) -> None:
        """Store the authoritative Output document owner."""

        self._document = document

    def present(self, media_id: UUID, frame: VideoRepresentativeFrame) -> bool:
        """Present one bounded detached frame without changing media identity."""

        image = QImage(
            frame.pixels,
            frame.width,
            frame.height,
            frame.stride,
            QImage.Format.Format_RGB32,
        ).copy()
        if image.isNull():
            return False
        if max(image.width(), image.height()) > VIDEO_REPRESENTATIVE_FRAME_MAX_EDGE:
            image = image.scaled(
                VIDEO_REPRESENTATIVE_FRAME_MAX_EDGE,
                VIDEO_REPRESENTATIVE_FRAME_MAX_EDGE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return self._document.replace_representative_image(media_id, image)


__all__ = ["OutputVideoRepresentativeFramePresenter"]
