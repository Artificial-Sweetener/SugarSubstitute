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

"""Provide the shared thumbnail-picker base used by image and mask pickers."""

from __future__ import annotations

import os
from typing import Any, Callable

from sugarsubstitute_shared.localization import ApplicationText, app_text
from substitute.presentation.localization import LocalizedPushButton

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

try:
    from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - test-stub fallback only

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
        """Provide a no-op font helper when qfluentwidgets font utilities are unavailable."""


from substitute.presentation.shell.chrome_style import connect_theme_refresh
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    ensure_fluent_tooltip_filter,
    set_fluent_tooltip_text,
)

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


class HighlightLabel(QLabel):
    """Paint a rounded hover/press overlay above the current thumbnail."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize hover and press tracking for the thumbnail label."""

        super().__init__(*args, **kwargs)
        self._hovered = False
        self._pressed = False
        self._corner_radius = 8
        self.setMouseTracking(True)

    def setCornerRadius(self, corner_radius: int) -> None:
        """Update the rounded-corner radius used by the overlay."""

        self._corner_radius = corner_radius
        self.update()

    def enterEvent(self, event: Any) -> None:
        """Track hover entry so the highlight overlay can render."""

        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        """Clear hover and press state when the cursor leaves the thumbnail."""

        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Track press state for the thumbnail highlight overlay."""

        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Clear press state after a mouse release."""

        if self._pressed:
            self._pressed = False
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the hover/press overlay after the base label paint pass."""

        super().paintEvent(event)
        if not (self._hovered or self._pressed):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._pressed:
            highlight_color = QColor(80, 80, 80, int(0.32 * 255))
        else:
            highlight_color = QColor(100, 100, 100, int(0.20 * 255))
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(rect, self._corner_radius, self._corner_radius)
        painter.setBrush(highlight_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)


class ThumbnailPickerBase(QWidget):
    """Render the shared thumbnail, caption, button, and placeholder behavior."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        thumbnail_size: int = 352,
        corner_radius: int = 8,
        default_folder: str = "",
        placeholder_image: str | None = None,
        button_padding: int = 24,
        browse_button_text: ApplicationText = app_text("Browse Files"),
    ) -> None:
        """Initialize the shared thumbnail-picker widget structure."""

        super().__init__(parent)
        self.setMouseTracking(True)

        self.thumbnail_size = thumbnail_size
        self.corner_radius = corner_radius
        self.default_folder = default_folder
        self.shadow_space = 12
        self.button_padding = button_padding
        self._current_file_path: str | None = None
        self._placeholder_image_path: str | None = None
        self._caption_tooltip_filter: FluentToolTipFilter | None = None

        self.thumbnail = HighlightLabel(self)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setStyleSheet("border: none; background: none;")

        self.caption = QLabel(self)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setFont(self.caption, 13)
        self.caption.setText("")
        self.caption.hide()
        self._caption_tooltip_filter = ensure_fluent_tooltip_filter(
            self.caption,
            self.caption,
            show_delay_ms=600,
            cursor_anchor=True,
        )

        self.button = LocalizedPushButton(browse_button_text, self)

        v_layout = QVBoxLayout(self)
        v_layout.setSpacing(6)
        v_layout.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignCenter)

        self.thumb_caption_spacer = QSpacerItem(
            0,
            -8,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        v_layout.addSpacerItem(self.thumb_caption_spacer)
        v_layout.addWidget(self.caption, alignment=Qt.AlignmentFlag.AlignCenter)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.addSpacerItem(
            QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )
        h_layout.addWidget(self.button)
        h_layout.addSpacerItem(
            QSpacerItem(
                self.button_padding,
                0,
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Minimum,
            )
        )

        v_layout.addLayout(h_layout)
        self.setLayout(v_layout)

        self.setMinimumWidth(thumbnail_size + self.shadow_space + 32)
        self.setStyleSheet("background: transparent;")
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

        if placeholder_image is not None:
            self.set_placeholder_image(placeholder_image)
        else:
            self.thumbnail.clear()
            self.caption.setText("")

        self.thumbnail.mouseReleaseEvent = self._on_thumbnail_clicked  # type: ignore[method-assign]

    def _on_thumbnail_clicked(self, event: QMouseEvent) -> None:
        """Clear press styling and forward thumbnail clicks to the concrete picker."""

        QLabel.mouseReleaseEvent(self.thumbnail, event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.handle_thumbnail_click()

    def handle_thumbnail_click(self) -> None:
        """Handle a thumbnail click in the concrete picker."""

    def set_default_folder(self, folder_path: str) -> None:
        """Set the default directory used by file dialogs."""

        self.default_folder = folder_path

    def set_placeholder_image(self, image_path: str) -> None:
        """Display the configured placeholder image and clear selected-path state."""

        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            rounded = self._rounded_pixmap(pixmap, self.corner_radius)
            self._apply_display_pixmap(rounded, caption_text="", tooltip_text="")
            self._placeholder_image_path = image_path
            self._current_file_path = None
            layout = self.layout()
            if layout is not None:
                layout.activate()
            return

        self.thumbnail.clear()
        self.caption.setText("")
        self.caption.setFixedWidth(self.thumbnail_size - 4)
        self.caption.hide()
        self._placeholder_image_path = None
        self._current_file_path = None

    def _restore_placeholder_or_clear(self) -> None:
        """Restore the placeholder image or clear the thumbnail when no placeholder exists."""

        if self._placeholder_image_path:
            self.set_placeholder_image(self._placeholder_image_path)
            return

        self.thumbnail.clear()
        self.caption.setText("")
        self.caption.setFixedWidth(self.thumbnail_size - 8)
        set_fluent_tooltip_text(self.caption, "")
        self.caption.hide()
        self._current_file_path = None

    def _set_selected_file(
        self,
        file_path: str,
        pixmap_loader: Callable[[str], QPixmap],
    ) -> None:
        """Render one selected file path or fall back to placeholder/empty state."""

        pixmap = pixmap_loader(file_path)
        if pixmap.isNull():
            self._restore_placeholder_or_clear()
            return

        rounded = self._rounded_pixmap(pixmap, self.corner_radius)
        filename = os.path.basename(file_path)
        max_width = rounded.width()
        metrics = self.caption.fontMetrics()
        elided = metrics.elidedText(
            f"[{filename}]",
            Qt.TextElideMode.ElideMiddle,
            max_width,
        )
        self._apply_display_pixmap(
            rounded,
            caption_text=elided,
            tooltip_text=file_path,
        )
        self._current_file_path = file_path
        layout = self.layout()
        if layout is not None:
            layout.activate()

    def _apply_display_pixmap(
        self,
        pixmap: QPixmap,
        *,
        caption_text: str,
        tooltip_text: str,
    ) -> None:
        """Apply the current rounded pixmap, caption, and tooltip text."""

        self.thumbnail.setPixmap(pixmap)
        self.thumbnail.setFixedSize(pixmap.size())
        self.thumbnail.setCornerRadius(self.corner_radius)
        self.caption.setFixedWidth(pixmap.width())
        self.caption.setText(caption_text)
        set_fluent_tooltip_text(self.caption, tooltip_text)
        self.caption.setVisible(bool(caption_text))

    def _rounded_pixmap(self, pixmap: QPixmap, radius: int) -> QPixmap:
        """Return a rounded-corner pixmap with the existing drop-shadow treatment."""

        scaled = pixmap.scaledToWidth(
            self.thumbnail_size,
            Qt.TransformationMode.SmoothTransformation,
        )
        size = scaled.size()
        shadow_offset = 6
        shadow_alpha = 60

        result_size = size + QSize(shadow_offset * 2, shadow_offset * 2)
        result = QPixmap(result_size)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        shadow_rect = QRectF(shadow_offset, shadow_offset, size.width(), size.height())
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, radius, radius)
        painter.fillPath(shadow_path, QColor(0, 0, 0, shadow_alpha))

        image_rect = QRectF(0, 0, size.width(), size.height())
        path = QPainterPath()
        path.addRoundedRect(image_rect, radius, radius)
        painter.setClipPath(path.translated(shadow_offset, shadow_offset))
        painter.drawPixmap(shadow_offset, shadow_offset, scaled)
        painter.setClipping(False)
        painter.end()
        return result

    def current_file_path(self) -> str | None:
        """Return the current selected file path."""

        return self._current_file_path

    def _apply_theme_styles(self) -> None:
        """Reapply caption text color after theme changes."""

        self.caption.setStyleSheet(
            "color: #ffffff;" if isDarkTheme() else "color: #1d2329;"
        )
