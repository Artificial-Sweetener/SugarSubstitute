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

"""Render compact Danbooru wiki thumbnail tiles and hidden-state placeholders."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import QFrame, QLabel, QWidget
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from substitute.application.danbooru.content_models import (
    DanbooruImagePreviewState,
    DanbooruWikiImagePreview,
)

_THUMBNAIL_EDGE = 156
_HIDDEN_LABEL_TEXT = "Hidden by content preferences"
_UNAVAILABLE_LABEL_TEXT = "No preview"


class DanbooruWikiImageCard(QFrame):
    """Render one clickable Danbooru thumbnail tile or compact placeholder."""

    def __init__(
        self,
        *,
        preview: DanbooruWikiImagePreview,
        open_url: Callable[[str], bool],
        caption_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the compact image tile from one preview result."""

        super().__init__(parent)
        self._preview = preview
        self._open_url = open_url
        self._caption_text = caption_text
        self._source_pixmap = (
            QPixmap(str(preview.local_path))
            if preview.local_path is not None
            else QPixmap()
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("DanbooruWikiImageCard")
        self.setFixedSize(self._card_size())
        self.setStyleSheet(
            "QFrame#DanbooruWikiImageCard {"
            "  border: 1px solid rgba(127, 127, 127, 0.18);"
            "  border-radius: 0px;"
            "  background: rgba(127, 127, 127, 0.08);"
            "}"
        )
        self._build_layout()
        self._refresh_pixmap()
        self._apply_tooltip()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Rescale the preview image when the tile is resized."""

        super().resizeEvent(event)
        self._refresh_pixmap()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Open the source Danbooru post when the tile is clicked."""

        if event.button() is Qt.MouseButton.LeftButton:
            self._open_url(self._preview.canonical_post_url)
        super().mouseReleaseEvent(event)

    def _build_layout(self) -> None:
        """Create the compact tile surface for image and placeholder states."""

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setGeometry(0, 0, self.width(), self.height())
        self._image_label.setStyleSheet(
            "QLabel { border-radius: 0px; background: rgba(127,127,127,0.05); }"
        )

        self._placeholder_label = CaptionLabel("", self)
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setWordWrap(True)
        self._placeholder_label.setGeometry(0, 0, self.width(), self.height())
        self._placeholder_label.setStyleSheet(
            "QLabel {"
            "  color: rgba(255,255,255,0.90);"
            "  background: rgba(0,0,0,0.22);"
            "  border-radius: 0px;"
            "  padding: 12px;"
            "}"
        )

        if self._preview.state is DanbooruImagePreviewState.READY:
            self._placeholder_label.hide()
            return
        self._image_label.hide()
        self._placeholder_label.setText(
            _HIDDEN_LABEL_TEXT
            if self._preview.state is DanbooruImagePreviewState.HIDDEN
            else _UNAVAILABLE_LABEL_TEXT
        )

    def _refresh_pixmap(self) -> None:
        """Scale the preview image into the compact thumbnail tile when available."""

        if self._preview.state is not DanbooruImagePreviewState.READY:
            return
        if self._source_pixmap.isNull():
            self._image_label.hide()
            self._placeholder_label.show()
            self._placeholder_label.setText(_UNAVAILABLE_LABEL_TEXT)
            return
        scaled = self._source_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    def _card_size(self) -> QSize:
        """Return the fixed tile size for one preview or placeholder state."""

        if self._preview.state is not DanbooruImagePreviewState.READY:
            return QSize(_THUMBNAIL_EDGE, _THUMBNAIL_EDGE)
        if not self._source_pixmap.isNull():
            return _height_bounded_size(self._source_pixmap.size())
        preview_size = _preview_size_from_metadata(self._preview)
        if preview_size is not None:
            return _height_bounded_size(preview_size)
        return QSize(_THUMBNAIL_EDGE, _THUMBNAIL_EDGE)

    def _apply_tooltip(self) -> None:
        """Expose caption and policy details without cluttering the tile body."""

        tooltip_parts: list[str] = []
        if self._caption_text:
            tooltip_parts.append(self._caption_text)
        if (
            self._preview.state is DanbooruImagePreviewState.HIDDEN
            and self._preview.hidden_reason
        ):
            tooltip_parts.append(self._preview.hidden_reason)
        elif self._preview.state is DanbooruImagePreviewState.UNAVAILABLE:
            tooltip_parts.append(
                self._preview.hidden_reason or "Preview image could not be loaded."
            )
        if tooltip_parts:
            self.setToolTip("\n".join(tooltip_parts))


def _preview_size_from_metadata(preview: DanbooruWikiImagePreview) -> QSize | None:
    """Return one source-size hint from preview metadata when both dimensions exist."""

    if preview.width is None or preview.height is None:
        return None
    return QSize(preview.width, preview.height)


def _height_bounded_size(source_size: QSize) -> QSize:
    """Return one preview size bounded by thumbnail height only."""

    if source_size.width() <= 0 or source_size.height() <= 0:
        return QSize(_THUMBNAIL_EDGE, _THUMBNAIL_EDGE)
    scaled = source_size.scaled(
        16_384,
        _THUMBNAIL_EDGE,
        Qt.AspectRatioMode.KeepAspectRatio,
    )
    return QSize(max(1, scaled.width()), _THUMBNAIL_EDGE)


__all__ = ["DanbooruWikiImageCard"]
