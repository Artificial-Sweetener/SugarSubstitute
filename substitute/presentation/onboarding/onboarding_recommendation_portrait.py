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

"""Render accessible full-bleed model recommendation portraits."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import QWidget
from qfluentwidgets import IndeterminateProgressRing  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedCheckBox,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    PORTRAIT_HEIGHT,
    PORTRAIT_WIDTH,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload


class RecommendationPortrait(QWidget):
    """Paint one full-bleed model image with an overlaid title wash."""

    selection_changed = Signal(bool)

    def __init__(
        self,
        *,
        pixmap: QPixmap | None,
        title: str,
        thumbnail_failed: bool,
        selected: bool,
        accessible_name: str,
        metadata: str = "",
        portrait_size: QSize | None = None,
        selectable: bool = True,
        parent: QWidget,
    ) -> None:
        """Store one decoded image and expose a native selectable control."""

        super().__init__(parent)
        if pixmap is not None and pixmap.isNull():
            raise ValueError("Recommendation portrait cannot use a null image.")
        self._pixmap = pixmap
        self._title = title
        self._metadata = metadata
        self._hovered = False
        self._selectable = selectable
        self.setObjectName("OnboardingRecommendationPortrait")
        self.setFixedSize(portrait_size or QSize(PORTRAIT_WIDTH, PORTRAIT_HEIGHT))
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if selectable else Qt.FocusPolicy.NoFocus
        )
        if selectable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(accessible_name)
        if metadata:
            self.setAccessibleDescription(metadata)
        self.busy_ring = IndeterminateProgressRing(self, start=pixmap is None)
        self.busy_ring.setObjectName("OnboardingRecommendationThumbnailBusy")
        self.busy_ring.setFixedSize(34, 34)
        self.busy_ring.setStrokeWidth(4)
        self.loading_label = LocalizedCaptionLabel(app_text("Loading preview…"), self)
        self.loading_label.setObjectName("OnboardingRecommendationThumbnailLoading")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unavailable_label = LocalizedCaptionLabel(
            app_text("Preview unavailable"), self
        )
        self.unavailable_label.setObjectName(
            "OnboardingRecommendationThumbnailUnavailable"
        )
        self.unavailable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unavailable_label.hide()
        self.checkbox = LocalizedCheckBox("", self)
        self.checkbox.setObjectName("OnboardingRecommendationPortraitCheck")
        self.checkbox.setAccessibleName(accessible_name)
        self.checkbox.setChecked(selected)
        self.checkbox.setVisible(selectable)
        self.checkbox.toggled.connect(self._selection_toggled)
        self._position_checkbox()
        self._position_thumbnail_status()
        if pixmap is not None:
            self.busy_ring.hide()
            self.loading_label.hide()
        elif thumbnail_failed:
            self.set_thumbnail_unavailable()

    def source_size(self) -> QSize:
        """Return the decoded source size used by rendered qualification."""

        return self._pixmap.size() if self._pixmap is not None else QSize()

    def thumbnail_is_loading(self) -> bool:
        """Return whether the portrait is waiting for its image payload."""

        return not self.busy_ring.isHidden()

    def thumbnail_is_unavailable(self) -> bool:
        """Return whether loading settled without a usable preview."""

        return not self.unavailable_label.isHidden()

    def set_thumbnail(self, thumbnail: ThumbnailAsset) -> bool:
        """Decode and display one asynchronously loaded thumbnail payload."""

        pixmap = thumbnail_pixmap(thumbnail)
        if pixmap is None:
            self.set_thumbnail_unavailable()
            return False
        self._pixmap = pixmap
        self.busy_ring.stop()
        self.busy_ring.hide()
        self.loading_label.hide()
        self.unavailable_label.hide()
        self.update()
        return True

    def set_thumbnail_unavailable(self) -> None:
        """Replace the busy indicator with a settled preview fallback."""

        self.busy_ring.stop()
        self.busy_ring.hide()
        self.loading_label.hide()
        self.unavailable_label.show()
        self.update()

    def is_selected(self) -> bool:
        """Return whether the portrait's native checkbox is selected."""

        return bool(self.checkbox.isChecked())

    def set_selected(self, selected: bool) -> None:
        """Restore explicit selection without replacing the native control."""

        self.checkbox.setChecked(selected)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint cropped media, the graduated wash, and title as one surface."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        bounds = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(bounds, 14, 14)
        painter.setClipPath(clip)
        if self._pixmap is None:
            painter.fillRect(bounds, QColor(255, 255, 255, 12))
        else:
            painter.drawPixmap(
                bounds, self._pixmap, _cover_source_rect(self._pixmap, bounds)
            )
        gradient = QLinearGradient(
            QPointF(0, bounds.height() * 0.42), QPointF(0, bounds.height())
        )
        gradient.setColorAt(0.0, QColor(6, 9, 14, 0))
        gradient.setColorAt(0.56, QColor(6, 9, 14, 34 if not self._hovered else 58))
        gradient.setColorAt(0.78, QColor(6, 9, 14, 132 if not self._hovered else 166))
        gradient.setColorAt(1.0, QColor(6, 9, 14, 232))
        painter.fillRect(bounds, gradient)
        painter.setPen(QColor(248, 249, 252))
        title_font = QFont(self.font())
        title_font.setPointSizeF(13.0)
        title_font.setWeight(QFont.Weight.Bold)
        painter.setFont(title_font)
        title_bottom_margin = 34 if self._metadata else 15
        title_bounds = bounds.adjusted(16, 16, -16, -title_bottom_margin)
        painter.drawText(
            title_bounds,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignBottom
            | Qt.TextFlag.TextWordWrap,
            self._title,
        )
        if self._metadata:
            metadata_font = QFont(self.font())
            metadata_font.setPointSizeF(9.5)
            metadata_font.setWeight(QFont.Weight.Medium)
            painter.setFont(metadata_font)
            painter.setPen(QColor(248, 249, 252, 210))
            painter.drawText(
                bounds.adjusted(16, 16, -16, -12),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                self._metadata,
            )

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802
        """Strengthen the title wash while the portrait is hovered."""

        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        """Restore the resting title wash after pointer departure."""

        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Toggle selection when the user clicks the image surface."""

        if self._selectable and event.button() is Qt.MouseButton.LeftButton:
            self.checkbox.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Toggle selection with Space or Enter from keyboard focus."""

        if self._selectable and event.key() in {
            Qt.Key.Key_Space,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        }:
            self.checkbox.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Keep the selection control inset from the portrait's top-right edge."""

        self._position_checkbox()
        self._position_thumbnail_status()
        super().resizeEvent(event)

    def _selection_toggled(self, selected: bool) -> None:
        """Repaint selection affordances and publish the explicit choice."""

        self.update()
        self.selection_changed.emit(selected)

    def _position_checkbox(self) -> None:
        """Place the native checkbox above the painted media and wash."""

        self.checkbox.setGeometry(self.width() - 42, 12, 30, 30)
        self.checkbox.raise_()

    def _position_thumbnail_status(self) -> None:
        """Center pending or failed state without covering the title."""

        status_center_y = int(self.height() * 0.32)
        self.busy_ring.move(
            (self.width() - self.busy_ring.width()) // 2,
            status_center_y - (self.busy_ring.height() // 2),
        )
        self.unavailable_label.setGeometry(16, 0, self.width() - 32, self.height() - 34)
        self.loading_label.setGeometry(
            16,
            status_center_y + 20,
            self.width() - 32,
            28,
        )
        self.busy_ring.raise_()
        self.loading_label.raise_()
        self.unavailable_label.raise_()


def thumbnail_pixmap(thumbnail: ThumbnailAsset) -> QPixmap | None:
    """Decode one prepared payload into a non-null GUI pixmap."""

    image = image_from_qt_thumbnail_payload(
        width=thumbnail.width,
        height=thumbnail.height,
        qt_format=thumbnail.qt_format,
        bytes_per_line=thumbnail.bytes_per_line,
        payload=thumbnail.payload,
    )
    if image is None or image.isNull():
        return None
    pixmap = QPixmap.fromImage(image)
    return pixmap if not pixmap.isNull() else None


def _cover_source_rect(pixmap: QPixmap, target: QRectF) -> QRectF:
    """Return a centered source crop that fills the portrait target."""

    source_width = float(pixmap.width())
    source_height = float(pixmap.height())
    target_ratio = target.width() / target.height()
    source_ratio = source_width / source_height
    if source_ratio > target_ratio:
        crop_width = source_height * target_ratio
        return QRectF((source_width - crop_width) / 2, 0, crop_width, source_height)
    crop_height = source_width / target_ratio
    return QRectF(0, (source_height - crop_height) / 2, source_width, crop_height)
