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

"""Compose the editable download cart and its fixed summary."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
)

from sugarsubstitute_shared.localization import app_text

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_recommendations import ModelInstallPlan
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
)

from substitute.presentation.onboarding.onboarding_download_cart_card import (
    DownloadCartCard,
)
from substitute.presentation.onboarding.onboarding_download_summary import (
    DownloadSummaryPanel,
)
from substitute.presentation.onboarding.onboarding_model_card_layout import (
    ModelCardLayout,
)


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
        self.content_column.setMinimumWidth(0)
        self.content_column.setMaximumWidth(1082)
        outer_layout = self.layout()
        if isinstance(outer_layout, QHBoxLayout):
            outer_layout.setStretch(0, 0)
            outer_layout.setStretch(1, 1)
            outer_layout.setStretch(2, 0)
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
        self.cards_scroll.setFixedHeight(CARD_HEIGHT * 2)
        self.cards_host = QWidget(self.cards_scroll)
        self.cards_host.setObjectName("OnboardingDownloadCardsHost")
        self.cards_layout = ModelCardLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_scroll.setWidget(self.cards_host)
        self.body_layout.addWidget(self.cards_scroll)
        self._cards: list[DownloadCartCard] = []
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
        for item, card in visible_items:
            if card is None:
                continue
            widget = DownloadCartCard(item=item, card=card, parent=self.cards_host)
            widget.remove_requested.connect(self.remove_requested)
            self.cards_layout.addWidget(widget)
            self._cards.append(widget)
        self.cards_host.updateGeometry()
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
        self._cards.clear()
        self.cards_host.setMinimumHeight(0)
