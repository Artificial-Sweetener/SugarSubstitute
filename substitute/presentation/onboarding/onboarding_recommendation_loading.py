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

"""Build the stable ten-card loading composition for model recommendations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QVBoxLayout, QWidget
from qfluentwidgets import IndeterminateProgressRing  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    PORTRAIT_HEIGHT,
    PORTRAIT_WIDTH,
)


class RecommendationLoadingGallery:
    """Own loading-card construction and progress-ring lifetime."""

    def __init__(self, *, host: QWidget, grid: QGridLayout) -> None:
        """Bind the loading composition to the recommendation card host."""

        self._host = host
        self._grid = grid
        self._rings: list[IndeterminateProgressRing] = []

    def build(self) -> None:
        """Build a complete 5×2 skeleton without delaying page navigation."""

        accessible_name = render_application_text(app_text("Loading recommendations…"))
        self._host.setMinimumHeight(CARD_HEIGHT)
        for index in range(10):
            card = QFrame(self._host)
            card.setObjectName("OnboardingRecommendationLoadingCard")
            card.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(7)

            portrait = QFrame(card)
            portrait.setObjectName("OnboardingRecommendationLoadingPortrait")
            portrait.setFixedSize(PORTRAIT_WIDTH, PORTRAIT_HEIGHT)
            portrait_layout = QVBoxLayout(portrait)
            portrait_layout.setContentsMargins(0, 0, 0, 0)
            portrait_layout.addStretch(1)
            ring = IndeterminateProgressRing(portrait, start=True)
            ring.setObjectName("OnboardingRecommendationLoadingBusy")
            ring.setAccessibleName(accessible_name)
            ring.setFixedSize(34, 34)
            ring.setStrokeWidth(4)
            portrait_layout.addWidget(ring, alignment=Qt.AlignmentFlag.AlignHCenter)
            portrait_layout.addStretch(1)
            card_layout.addWidget(portrait)

            self._grid.addWidget(card, index // 5, index % 5)
            self._rings.append(ring)

    def clear(self) -> None:
        """Stop every loading animation before its widgets are removed."""

        for ring in self._rings:
            ring.stop()
        self._rings.clear()


__all__ = [
    "PORTRAIT_HEIGHT",
    "PORTRAIT_WIDTH",
    "RecommendationLoadingGallery",
]
