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

"""Characterization tests for shared thumbnail-picker behavior."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.panel.widgets.fields.thumbnail_preview_surface import (
    ThumbnailPreviewSurface,
)


class _SolidLivePreview(QWidget):
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

    def paintEvent(self, event: object) -> None:
        """Fill the preview with the same pixels as the static fixture."""

        del event
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


def _render_transparent(widget: QWidget) -> QImage:
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


def _qapp() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_thumbnail_picker_caption_uses_fluent_tooltip_filter() -> None:
    """Caption tooltip behavior should use the shared QFluent owner."""

    _qapp()
    sys.modules.pop("sugarsubstitute_shared.presentation.fluent_tooltips", None)
    sys.modules.pop(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base",
        None,
    )
    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )

    picker = mod.ThumbnailPickerBase()

    assert isinstance(
        picker._caption_tooltip_filter,
        mod.FluentToolTipFilter,
    )
    assert picker._caption_tooltip_filter._tooltipDelay == 600

    picker.close()
    picker.deleteLater()


def test_restore_placeholder_or_clear_prefers_placeholder_when_available() -> None:
    """Shared restore helper should route back through the configured placeholder path."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )
    placeholder_calls: list[str] = []
    fake = SimpleNamespace(
        _placeholder_image_path="C:/images/default.png",
        set_placeholder_image=lambda path: placeholder_calls.append(path),
    )

    mod.ThumbnailPickerBase._restore_placeholder_or_clear(fake)

    assert placeholder_calls == ["C:/images/default.png"]


def test_restore_placeholder_or_clear_resets_thumbnail_state_without_placeholder() -> (
    None
):
    """Shared restore helper should clear thumbnail, caption, and current path state."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )
    _qapp()
    picker = mod.ThumbnailPickerBase()
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
    picker.close()


def test_static_thumbnail_keeps_historical_frame_geometry_and_caption_width() -> None:
    """New live-preview support must not alter the original picker presentation."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.widgets.fields.thumbnail_picker_base"
    )
    _qapp()
    picker = mod.ThumbnailPickerBase(thumbnail_size=352, corner_radius=8)
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
    picker.close()


def test_live_thumbnail_uses_the_exact_historical_antialiased_corner_mask() -> None:
    """Live document pixels must match the original rounded frame pixel-for-pixel."""

    _qapp()
    static_surface = ThumbnailPreviewSurface(
        thumbnail_width=100,
        corner_radius=8,
    )
    live_surface = ThumbnailPreviewSurface(
        thumbnail_width=100,
        corner_radius=8,
    )
    static_surface.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    live_surface.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    source = QPixmap(100, 50)
    source.fill(QColor("magenta"))
    static_surface.set_static_pixmap(source)
    live_preview = _SolidLivePreview()
    live_surface.set_live_content(live_preview)

    static_pixels = _render_transparent(static_surface)
    live_pixels = _render_transparent(live_surface)

    assert static_pixels == live_pixels
    assert static_pixels.pixelColor(10, 6).alpha() not in {0, 255}
    assert live_preview.corner_radius == 8
    static_surface.close()
    live_surface.close()
