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

"""Render portrait model recommendations and exact download review."""

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
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    IndeterminateProgressRing,
)

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
)

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
    model_family_presentation,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedCheckBox,
    LocalizedPushButton,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)
from substitute.presentation.onboarding.onboarding_recommendation_loading import (
    PORTRAIT_HEIGHT as _PORTRAIT_HEIGHT,
    PORTRAIT_WIDTH as _PORTRAIT_WIDTH,
    RecommendationLoadingGallery,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload


class RecommendationPortrait(QWidget):
    """Paint one full-bleed 4:5 model image with an overlaid title wash."""

    selection_changed = Signal(bool)

    def __init__(
        self,
        *,
        pixmap: QPixmap | None,
        title: str,
        thumbnail_failed: bool,
        selected: bool,
        accessible_name: str,
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
        self._hovered = False
        self._selectable = selectable
        self.setObjectName("OnboardingRecommendationPortrait")
        self.setFixedSize(portrait_size or QSize(_PORTRAIT_WIDTH, _PORTRAIT_HEIGHT))
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if selectable else Qt.FocusPolicy.NoFocus
        )
        if selectable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(accessible_name)
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

        pixmap = _pixmap_from_thumbnail(thumbnail)
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
        font = QFont(self.font())
        font.setPointSizeF(15.5)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        title_bounds = bounds.adjusted(16, 16, -16, -15)
        painter.drawText(
            title_bounds,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignBottom
            | Qt.TextFlag.TextWordWrap,
            self._title,
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

        self.busy_ring.move(
            (self.width() - self.busy_ring.width()) // 2,
            (self.height() - self.busy_ring.height()) // 2 - 10,
        )
        self.unavailable_label.setGeometry(16, 0, self.width() - 32, self.height() - 34)
        self.loading_label.setGeometry(
            16,
            (self.height() // 2) + 18,
            self.width() - 32,
            28,
        )
        self.busy_ring.raise_()
        self.loading_label.raise_()
        self.unavailable_label.raise_()


class RecommendationCard(QFrame):
    """Render one selectable portrait recommendation with compact metadata."""

    selection_changed = Signal(int, bool)
    link_requested = Signal(str)

    def __init__(
        self,
        card: RecommendationCardAsset,
        *,
        selected: bool,
        parent: QWidget,
    ) -> None:
        """Build an accessible card from provider-safe text and decoded media."""

        super().__init__(parent)
        recommendation = card.recommendation
        self._version_id = recommendation.version_id
        self.setObjectName("OnboardingRecommendationCard")
        self.setProperty("selected", selected)
        accessible_name = render_application_text(
            app_text("%1 model recommendation", recommendation.model_name)
        )
        self.setAccessibleName(accessible_name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
        pixmap = (
            _pixmap_from_thumbnail(card.thumbnail)
            if card.thumbnail is not None
            else None
        )
        self.portrait = RecommendationPortrait(
            pixmap=pixmap,
            title=recommendation.model_name,
            thumbnail_failed=card.thumbnail_failed
            or (card.thumbnail is not None and pixmap is None),
            selected=selected,
            accessible_name=accessible_name,
            parent=self,
        )
        self.checkbox = self.portrait.checkbox
        self.checkbox.setObjectName(
            f"OnboardingRecommendationSelect_{recommendation.version_id}"
        )
        self.portrait.selection_changed.connect(self._set_selected)
        layout.addWidget(self.portrait)
        self.link_button = LocalizedPushButton(app_text("View on CivitAI"), self)
        self.link_button.setObjectName(
            f"OnboardingRecommendationLink_{recommendation.version_id}"
        )
        self.link_button.setAccessibleName(
            render_application_text(
                app_text("View %1 on CivitAI", recommendation.model_name)
            )
        )
        self.link_button.clicked.connect(
            lambda: self.link_requested.emit(recommendation.model_page_url)
        )
        layout.addWidget(self.link_button)

    def set_thumbnail(self, thumbnail: ThumbnailAsset) -> bool:
        """Install one completed image into this card's portrait."""

        return self.portrait.set_thumbnail(thumbnail)

    def set_thumbnail_unavailable(self) -> None:
        """Settle this card's image area when loading fails."""

        self.portrait.set_thumbnail_unavailable()

    def _set_selected(self, selected: bool) -> None:
        """Project selection onto the card frame and notify the presenter."""

        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.selection_changed.emit(self._version_id, selected)


class ModelRecommendationPage(OnboardingPageFrame):
    """Show three large portrait recommendations for one missing family."""

    selection_changed = Signal(int, bool)
    link_requested = Signal(str)
    skip_family_requested = Signal()
    find_own_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the reusable family recommendation surface and skip actions."""

        super().__init__(
            title=app_text("Popular models this month"),
            description=app_text(
                "Choose a model to download, skip this family, or find your own models."
            ),
            icon=FIF.PHOTO,
            eyebrow=app_text("CivitAI recommendations"),
            parent=parent,
        )
        self.setObjectName("OnboardingModelRecommendationPage")
        self._family_id: ModelFamilyId | None = None
        self._cards_by_version_id: dict[int, RecommendationCard] = {}
        self.family_label = LocalizedBodyLabel("", self)
        self.family_label.setObjectName("OnboardingRecommendationFamily")
        self.body_layout.addWidget(self.family_label)
        self.card_host = QWidget(self)
        self.card_grid = QGridLayout(self.card_host)
        self.card_grid.setContentsMargins(0, 0, 0, 0)
        self.card_grid.setHorizontalSpacing(14)
        self._loading_gallery = RecommendationLoadingGallery(
            host=self.card_host,
            grid=self.card_grid,
        )
        self.body_layout.addWidget(self.card_host)
        self.loading_row = QWidget(self)
        loading_layout = QHBoxLayout(self.loading_row)
        loading_layout.setContentsMargins(0, 18, 0, 18)
        loading_layout.setSpacing(12)
        self.loading_ring = IndeterminateProgressRing(self.loading_row, start=False)
        self.loading_ring.setFixedSize(26, 26)
        self.loading_ring.setAccessibleName(
            render_application_text(app_text("Loading recommendations…"))
        )
        self.loading_status = LocalizedBodyLabel("", self.loading_row)
        self.loading_status.setWordWrap(True)
        loading_layout.addWidget(self.loading_ring)
        loading_layout.addWidget(self.loading_status, 1)
        self.loading_row.hide()
        self.body_layout.addWidget(self.loading_row)
        self.empty_label = LocalizedCaptionLabel(
            app_text(
                "CivitAI did not return a safe portrait for this family. You can skip it or find your own models."
            ),
            self,
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.body_layout.addWidget(self.empty_label)
        actions = QHBoxLayout()
        self.skip_button = LocalizedPushButton("", self)
        self.skip_button.setObjectName("OnboardingRecommendationSkipButton")
        self.find_own_button = LocalizedPushButton(
            app_text("I'll find my own models"), self
        )
        self.find_own_button.setObjectName("OnboardingFindOwnModelsButton")
        actions.addWidget(self.skip_button)
        actions.addWidget(self.find_own_button)
        actions.addStretch(1)
        self.body_layout.addLayout(actions)
        self.skip_button.clicked.connect(self.skip_family_requested.emit)
        self.find_own_button.clicked.connect(self.find_own_requested.emit)

    def show_loading(self, family_id: ModelFamilyId) -> None:
        """Show the final three-card composition while CivitAI responds."""

        self._clear_cards()
        self._set_family(family_id)
        self._loading_gallery.build()
        self.loading_ring.stop()
        self.loading_row.hide()
        self.card_host.show()
        self.empty_label.hide()
        self.skip_button.hide()
        self.find_own_button.hide()

    def show_failure(
        self,
        family_id: ModelFamilyId,
        message: ApplicationText,
    ) -> None:
        """Keep provider failure on the page where the user can recover."""

        self._clear_cards()
        self._set_family(family_id)
        self.loading_ring.stop()
        self.loading_ring.hide()
        apply_application_text(self.loading_status, message)
        self.loading_row.show()
        self.card_host.hide()
        self.empty_label.hide()
        self.skip_button.hide()
        self.find_own_button.show()

    def current_family(self) -> ModelFamilyId | None:
        """Return the family currently represented by the card grid."""

        return self._family_id

    def visible_cards(self) -> tuple[RecommendationCard, ...]:
        """Return the currently rendered cards for qualification and accessibility."""

        return tuple(self._cards_by_version_id.values())

    def set_recommendations(
        self,
        page: FamilyRecommendationPage,
        *,
        selected_version_ids: frozenset[int],
    ) -> None:
        """Replace cards with one missing-family page and retained selections."""

        self._clear_cards()
        self._set_family(page.family_id)
        self.loading_ring.stop()
        self.loading_row.hide()
        self.card_host.show()
        self.skip_button.show()
        self.find_own_button.show()
        rendered = 0
        for index, card in enumerate(page.cards[:3]):
            widget = RecommendationCard(
                card,
                selected=card.recommendation.version_id in selected_version_ids,
                parent=self.card_host,
            )
            widget.selection_changed.connect(self.selection_changed)
            widget.link_requested.connect(self.link_requested)
            self.card_grid.addWidget(widget, 0, index)
            self._cards_by_version_id[card.recommendation.version_id] = widget
            rendered += 1
        self.empty_label.setVisible(rendered == 0)

    def _clear_cards(self) -> None:
        """Remove prior cards before showing another family state."""

        self._loading_gallery.clear()
        _clear_layout(self.card_grid)
        self.card_host.setMinimumHeight(0)
        self._cards_by_version_id.clear()

    def _set_family(self, family_id: ModelFamilyId) -> None:
        """Render the family heading and corresponding skip action."""

        self._family_id = family_id
        presentation = model_family_presentation(family_id)
        if family_id is ModelFamilyId.SDXL:
            self.family_label.setText(app_text("Illustrious · SDXL compatible"))
        else:
            self.family_label.setText(presentation.name)
        apply_application_text(
            self.skip_button,
            app_text("Skip %1", presentation.name),
        )

    def set_thumbnail(self, version_id: int, thumbnail: ThumbnailAsset) -> bool:
        """Install a completed thumbnail when its card is currently visible."""

        card = self._cards_by_version_id.get(version_id)
        return card.set_thumbnail(thumbnail) if card is not None else False

    def set_thumbnail_unavailable(self, version_id: int) -> bool:
        """Settle one visible card whose thumbnail request failed."""

        card = self._cards_by_version_id.get(version_id)
        if card is None:
            return False
        card.set_thumbnail_unavailable()
        return True


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


def _pixmap_from_thumbnail(thumbnail: ThumbnailAsset) -> QPixmap | None:
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


def _clear_layout(layout: QGridLayout) -> None:
    """Delete every prior recommendation card before rendering another family."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
