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

"""Verify shared thumbnail-picker state and rendered surface contracts."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QRegion,
)
from PySide6.QtWidgets import QWidget

from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter
from substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base import (
    ThumbnailPickerBase,
)
from substitute.presentation.editor.panel.widgets.fields.thumbnail_preview_surface import (
    ThumbnailPreviewSurface,
)
from tests.presentation.editor.panel.widgets.thumbnail_picker.support import (
    ThumbnailPickerOwner,
)


class SolidLivePreview(QWidget):
    """Paint deterministic pixels through the live thumbnail path."""

    def __init__(self) -> None:
        """Create an unclipped preview awaiting surface presentation policy."""

        super().__init__()
        self.corner_radius = 0

    def set_thumbnail_corner_radius(self, radius: int) -> None:
        """Accept the corner geometry owned by the thumbnail surface."""

        self.corner_radius = radius

    def sizeHint(self) -> QSize:
        """Return the historical test thumbnail content size."""

        return QSize(100, 50)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Fill the preview with the same pixels as the static fixture."""

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(self.rect()),
            self.corner_radius,
            self.corner_radius,
        )
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor("magenta"))
        painter.end()


def render_transparent(widget: QWidget) -> QImage:
    """Render one widget tree into a transparent deterministic image."""

    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(
        painter,
        QPoint(),
        QRegion(),
        QWidget.RenderFlag.DrawChildren,
    )
    painter.end()
    return image


def test_caption_uses_fluent_tooltip_filter(
    thumbnail_owner: ThumbnailPickerOwner,
) -> None:
    """Caption tooltip behavior should use the shared Fluent owner."""

    picker = thumbnail_owner.own(ThumbnailPickerBase())

    assert isinstance(picker._caption_tooltip_filter, FluentToolTipFilter)
    assert picker._caption_tooltip_filter._tooltipDelay == 600


def test_restore_prefers_configured_placeholder(
    thumbnail_owner: ThumbnailPickerOwner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore through the configured placeholder path when one is available."""

    picker = thumbnail_owner.own(ThumbnailPickerBase())
    placeholder_calls: list[str] = []
    picker._placeholder_image_path = "C:/images/default.png"
    monkeypatch.setattr(picker, "set_placeholder_image", placeholder_calls.append)

    picker._restore_placeholder_or_clear()

    assert placeholder_calls == ["C:/images/default.png"]


def test_restore_clears_thumbnail_state_without_placeholder(
    thumbnail_owner: ThumbnailPickerOwner,
) -> None:
    """Restore clears thumbnail, caption, and path state without a placeholder."""

    picker = thumbnail_owner.own(ThumbnailPickerBase())
    picker._current_file_path = "C:/images/chosen.png"
    picker.caption.setText("existing")
    picker.caption.setToolTip("existing")
    picker.caption.show()

    picker._restore_placeholder_or_clear()

    pixmap = picker.thumbnail.pixmap()
    assert pixmap is None or pixmap.isNull()
    assert picker.caption.text() == ""
    assert picker.caption.width() == 344
    assert picker.caption.toolTip() == ""
    assert picker.caption.isHidden()
    assert picker.current_file_path() is None


def test_static_thumbnail_preserves_frame_geometry_and_caption_width(
    thumbnail_owner: ThumbnailPickerOwner,
) -> None:
    """Static presentation retains the established picker geometry."""

    picker = thumbnail_owner.own(
        ThumbnailPickerBase(thumbnail_size=352, corner_radius=8)
    )
    source = QPixmap(176, 88)
    source.fill(QColor("magenta"))

    picker._apply_display_pixmap(
        source,
        caption_text="[source.png]",
        tooltip_text="source.png",
    )

    assert picker.preview_surface.size() == QSize(364, 188)
    assert picker.thumbnail.size() == QSize(364, 188)
    assert picker.caption.width() == 364
    framed = picker.thumbnail.pixmap()
    assert framed is not None and framed.size() == QSize(364, 188)
    assert framed.toImage().pixelColor(0, 0).alpha() == 0
    assert framed.toImage().pixelColor(182, 94).red() > 200


def test_live_thumbnail_uses_static_antialiased_corner_mask(
    thumbnail_owner: ThumbnailPickerOwner,
) -> None:
    """Live pixels match the static rounded frame pixel-for-pixel."""

    static_surface = thumbnail_owner.own(
        ThumbnailPreviewSurface(thumbnail_width=100, corner_radius=8)
    )
    live_surface = thumbnail_owner.own(
        ThumbnailPreviewSurface(thumbnail_width=100, corner_radius=8)
    )
    static_surface.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    live_surface.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    source = QPixmap(100, 50)
    source.fill(QColor("magenta"))
    static_surface.set_static_pixmap(source)
    live_preview = SolidLivePreview()
    live_surface.set_live_content(live_preview)

    static_pixels = render_transparent(static_surface)
    live_pixels = render_transparent(live_surface)

    assert static_pixels == live_pixels
    assert static_pixels.pixelColor(10, 6).alpha() not in {0, 255}
    assert live_preview.corner_radius == 8
