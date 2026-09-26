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

"""Build deterministic image and metadata inputs for video qualification."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter

from substitute.domain.output_media import OutputMediaKind
from substitute.domain.workflow import ImageMeta


def qualification_image(size: QSize) -> QImage:
    """Create one project-owned image fixture with visible spatial detail."""

    image = QImage(size, QImage.Format.Format_RGB32)
    gradient = QLinearGradient(0, 0, size.width(), size.height())
    gradient.setColorAt(0.0, QColor("#e85d75"))
    gradient.setColorAt(0.5, QColor("#7a5cff"))
    gradient.setColorAt(1.0, QColor("#38bdf8"))
    painter = QPainter(image)
    painter.fillRect(image.rect(), gradient)
    painter.setPen(QColor("white"))
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "IMAGE")
    painter.end()
    return image


def qualification_metadata(
    path: Path,
    kind: OutputMediaKind,
    *,
    duration_seconds: float | None = None,
) -> ImageMeta:
    """Create one complete final-media record for the production canvas."""

    return ImageMeta(
        workflow_name="Video qualification",
        cube_name="Mixed output",
        image_number=1,
        suffix="",
        path=path.as_posix(),
        source_key="qualification",
        source_label="Mixed output",
        media_kind=kind,
        duration_seconds=duration_seconds,
        mime_type="video/mp4" if kind is OutputMediaKind.VIDEO else "image/png",
    )


__all__ = ["qualification_image", "qualification_metadata"]
