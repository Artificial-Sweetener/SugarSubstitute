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

"""Render selected model downloads as an editable checkout."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    TransparentToolButton,
)

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_recommendations import ModelInstallFile, ModelInstallPlan
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    THUMBNAIL_SIZE,
)
from substitute.shared.qt_thumbnail_codec import image_from_qt_thumbnail_payload

_REMOVE_BUTTON_STYLE = """
QToolButton {
    background-color: rgba(10, 12, 18, 194);
    border: 1px solid rgba(255, 255, 255, 158);
    border-radius: 7px;
}
QToolButton:hover {
    background-color: rgba(188, 42, 72, 240);
    border-color: rgba(255, 255, 255, 224);
}
QToolButton:pressed {
    background-color: rgba(151, 27, 52, 250);
}
"""


class DownloadCartCard(QFrame):
    """Present one exact selected model as a removable checkout item."""

    remove_requested = Signal(int)

    def __init__(
        self,
        *,
        item: ModelInstallFile,
        card: RecommendationCardAsset,
        parent: QWidget,
    ) -> None:
        """Build a title-washed portrait with concise family and size metadata."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadCartCard")
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        pixmap = _card_pixmap(card)
        self.portrait = RecommendationPortrait(
            pixmap=pixmap,
            title=item.display_name,
            thumbnail_failed=card.thumbnail_failed,
            selected=False,
            accessible_name=item.display_name,
            metadata=f"{item.family_id.value.upper()}  ·  {format_model_size(item.size_bytes)}",
            portrait_size=THUMBNAIL_SIZE,
            selectable=False,
            parent=self,
        )
        if card.thumbnail is not None and pixmap is None:
            self.portrait.set_thumbnail_unavailable()
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignCenter)
        self.remove_button = TransparentToolButton(FIF.DELETE, self.portrait)
        self.remove_button.setObjectName(f"OnboardingRemoveModel_{item.version_id}")
        self.remove_button.setProperty("onboardingCardRemove", True)
        self.remove_button.setFixedSize(28, 28)
        self.remove_button.setIconSize(QSize(18, 18))
        self.remove_button.setStyleSheet(_REMOVE_BUTTON_STYLE)
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.move(self.portrait.width() - 38, 10)
        accessible_name = render_application_text(
            app_text("Remove %1", item.display_name)
        )
        set_fluent_tooltip_text(self.remove_button, accessible_name)
        self.remove_button.setAccessibleName(accessible_name)
        self.remove_button.clicked.connect(
            lambda: self.remove_requested.emit(item.version_id)
        )
        self.remove_button.raise_()


class DownloadSummaryPanel(QFrame):
    """Summarize the editable cart without exposing a long absolute path."""

    def __init__(self, parent: QWidget) -> None:
        """Build model-count, transfer, storage, and destination values."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadSummaryPanel")
        self.setFixedWidth(500)
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(18)
        self.count_label = self._value(layout, app_text("Models"))
        self.total_label = self._value(layout, app_text("Download"))
        self.available_label = self._value(layout, app_text("Free space"))

    def set_plan(self, plan: ModelInstallPlan) -> None:
        """Refresh the visible checkout totals for one exact plan."""

        self.count_label.setText(str(len(plan.files)))
        self.total_label.setText(format_model_size(plan.total_bytes))
        self.available_label.setText(format_model_size(plan.available_bytes))
        destination = str(plan.model_root)
        set_fluent_tooltip_text(self, destination)
        self.setAccessibleDescription(destination)

    def _value(
        self,
        layout: QHBoxLayout,
        label: ApplicationText,
    ) -> LocalizedBodyLabel:
        """Add one compact labeled value to the summary."""

        column = QVBoxLayout()
        column.setSpacing(2)
        caption = LocalizedCaptionLabel(label, self)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(caption)
        value = LocalizedBodyLabel("", self)
        value.setObjectName("OnboardingDownloadSummaryValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(value)
        layout.addLayout(column, 1)
        return value


class ModelDownloadReviewPage(OnboardingPageFrame):
    """Review exact selected primary models as an editable cart."""

    remove_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build an approachable checkout with model cards and totals."""

        super().__init__(
            title=app_text("Review model downloads"),
            description=app_text("Remove anything you no longer want, then download."),
            icon=FIF.CHECKBOX,
            parent=parent,
        )
        self.setObjectName("OnboardingModelDownloadReviewPage")
        self.content_column.setMinimumWidth(1068)
        self.content_column.setMaximumWidth(1068)
        self.summary_panel = DownloadSummaryPanel(self.hero_panel)
        hero_layout = self.hero_panel.layout()
        if isinstance(hero_layout, QHBoxLayout):
            hero_layout.addWidget(
                self.summary_panel,
                alignment=Qt.AlignmentFlag.AlignVCenter,
            )
        self.cards_scroll = QScrollArea(self)
        self.cards_scroll.setObjectName("OnboardingDownloadCardsScroll")
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.cards_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.cards_scroll.setFixedHeight((CARD_HEIGHT * 2) + 10)
        self.cards_host = QWidget(self.cards_scroll)
        self.cards_host.setObjectName("OnboardingDownloadCardsHost")
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_scroll.setWidget(self.cards_host)
        self.body_layout.addWidget(self.cards_scroll)
        self._cards: list[DownloadCartCard] = []
        self._card_rows: list[QWidget] = []
        self.empty_label = LocalizedBodyLabel(
            app_text("Your model cart is empty."), self
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.body_layout.addWidget(self.empty_label)
        self.space_warning_label = LocalizedCaptionLabel("", self)
        self.space_warning_label.setObjectName("OnboardingDownloadSpaceWarning")
        self.space_warning_label.setWordWrap(True)
        self.space_warning_label.hide()
        self.body_layout.addWidget(self.space_warning_label)

    def set_plan(
        self,
        plan: ModelInstallPlan,
        cards: tuple[RecommendationCardAsset, ...],
    ) -> None:
        """Render exact selected cards and the resulting download totals."""

        self._clear_cards()
        cards_by_version = {card.recommendation.version_id: card for card in cards}
        visible_items = tuple(
            (item, cards_by_version.get(item.version_id)) for item in plan.files
        )
        visible_items = tuple(
            (item, card) for item, card in visible_items if card is not None
        )
        for row_start in range(0, len(visible_items), 5):
            row_host = QWidget(self)
            row_layout = QHBoxLayout(row_host)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)
            row_host.setFixedHeight(CARD_HEIGHT)
            row_layout.addStretch(1)
            for item, card in visible_items[row_start : row_start + 5]:
                if card is None:
                    continue
                widget = DownloadCartCard(item=item, card=card, parent=row_host)
                widget.remove_requested.connect(self.remove_requested)
                row_layout.addWidget(widget)
                self._cards.append(widget)
            row_layout.addStretch(1)
            self.cards_layout.addWidget(row_host)
            self._card_rows.append(row_host)
        row_count = (len(visible_items) + 4) // 5
        self.cards_host.setMinimumHeight(
            (row_count * CARD_HEIGHT) + (max(0, row_count - 1) * 10)
        )
        self.empty_label.setVisible(not plan.files)
        self.summary_panel.setVisible(bool(plan.files))
        self.summary_panel.set_plan(plan)
        self.space_warning_label.setVisible(not plan.has_sufficient_space)
        if not plan.has_sufficient_space:
            self.space_warning_label.setText(
                app_text("There is not enough free space for these models.")
            )

    def _clear_cards(self) -> None:
        """Remove prior checkout cards before rendering current selection state."""

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._card_rows.clear()
        self._cards.clear()
        self.cards_host.setMinimumHeight(0)


def _card_pixmap(card: RecommendationCardAsset) -> QPixmap | None:
    """Decode a retained exact-version thumbnail for checkout rendering."""

    if card.thumbnail is None:
        return None
    image = image_from_qt_thumbnail_payload(
        width=card.thumbnail.width,
        height=card.thumbnail.height,
        qt_format=card.thumbnail.qt_format,
        bytes_per_line=card.thumbnail.bytes_per_line,
        payload=card.thumbnail.payload,
    )
    if image is None or image.isNull():
        return None
    return QPixmap.fromImage(image)


def format_model_size(size_bytes: int) -> str:
    """Return a concise binary transfer size for review copy."""

    value = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size_bytes} B"


def download_action_text(plan: ModelInstallPlan) -> ApplicationText:
    """Return a fixed-footer action label that keeps total transfer cost visible."""

    return app_text(
        "%1 · %2",
        app_text("Download %1 models", len(plan.files)),
        format_model_size(plan.total_bytes),
    )


__all__ = ["ModelDownloadReviewPage", "download_action_text"]
