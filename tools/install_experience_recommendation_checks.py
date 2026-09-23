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

"""Verify recommendation-card geometry and installer viewport ownership."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QCheckBox, QWidget

from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.onboarding import OnboardingWindow
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)


def assert_recommendation_page(
    window: OnboardingWindow,
    family: ModelFamilyId,
    *,
    allow_unavailable: bool = False,
) -> None:
    """Require the centered eight-model grid and two coherent special choices."""

    card_widgets: list[QWidget] = []
    for index in range(window.model_recommendation_page.card_grid.count()):
        item = window.model_recommendation_page.card_grid.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is not None:
            card_widgets.append(widget)
    selectable = [
        checkbox
        for card in card_widgets
        for checkbox in card.findChildren(QCheckBox)
        if checkbox.objectName().startswith("OnboardingRecommendationSelect_")
    ]
    expected_checked = family is ModelFamilyId.UPSCALERS
    if len(selectable) != 8 or any(
        card.isChecked() != expected_checked for card in selectable
    ):
        raise RuntimeError(
            f"{family} recommendation cards do not match their default selection."
        )
    portraits = [
        portrait
        for card in card_widgets
        for portrait in card.findChildren(RecommendationPortrait)
    ]
    if len(portraits) != 8 or any(
        portrait.source_size().height() < 960
        and not (allow_unavailable and portrait.thumbnail_is_unavailable())
        for portrait in portraits
    ):
        raise RuntimeError(f"{family} recommendations lack real prepared thumbnails.")
    if len(card_widgets) != 10:
        raise RuntimeError(
            f"{family} recommendation grid does not contain ten choices."
        )
    row_tops = sorted({card.y() for card in card_widgets})
    for index, widget in enumerate(card_widgets):
        row = row_tops.index(widget.y())
        row_lefts = sorted(card.x() for card in card_widgets if card.y() == widget.y())
        column = row_lefts.index(widget.x())
        if (row, column) != (index // 5, index % 5):
            raise RuntimeError(f"{family} recommendation grid is not 5 by 2.")
    for card, portrait in zip(card_widgets[:8], portraits, strict=True):
        card_center = card.mapToGlobal(card.rect().center()).x()
        portrait_center = portrait.mapToGlobal(portrait.rect().center()).x()
        if abs(card_center - portrait_center) > 1:
            raise RuntimeError(
                f"{family} recommendation thumbnail is not centered: "
                f"card={card_center}, portrait={portrait_center}."
            )
    left = min(card.geometry().left() for card in card_widgets)
    right = max(card.geometry().right() for card in card_widgets)
    grid_center = (left + right) // 2
    host_center = window.model_recommendation_page.card_host.rect().center().x()
    if abs(grid_center - host_center) > 1:
        raise RuntimeError(f"{family} recommendation grid is not centered.")


def require_current_page_to_fit(window: OnboardingWindow, checkpoint: str) -> None:
    """Reject qualification states that spill beneath the fixed installer footer."""

    QApplication.processEvents()
    overflow = window.page_stage.verticalScrollBar().maximum()
    if overflow > 0:
        raise RuntimeError(
            f"{checkpoint} exceeds the installer viewport by {overflow} pixels."
        )
