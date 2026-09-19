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

"""Verify model choices wrap without losing reachable cards."""

from sugarsubstitute_shared.localization import app_text
import pytest
from substitute.application.model_recommendations import FamilyRecommendationPage
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.onboarding.onboarding_recommendation_pages import (
    ModelRecommendationPage,
)
from sugarsubstitute_shared.presentation.setup_page_stage import SetupPageStage
from tests.support.qt.lifecycle import ensure_qt_application, destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


@pytest.mark.parametrize("loading", (True, False))
@pytest.mark.parametrize(("width", "rows"), ((940, 3), (1104, 2)))
def test_recommendations_fit_stage(loading: bool, width: int, rows: int) -> None:
    """Keep all ten choices horizontally reachable at a compact viewport width."""
    ensure_qt_application()
    host = QWidget()
    host.setFixedSize(width, 548)
    stage = SetupPageStage(host)
    stage.setGeometry(host.rect())
    page = ModelRecommendationPage()
    stage.add_page(page)
    if loading:
        page.show_loading(ModelFamilyId.SDXL)
    else:
        page.set_recommendations(
            FamilyRecommendationPage(ModelFamilyId.SDXL, ()),
            selected_version_ids=frozenset(),
            use_own_model=False,
        )
    stage.show_page(page)
    host.show()
    try:
        wait_for_queued_qt_turn()
        stage.refresh_layout()
        wait_for_queued_qt_turn()
        cards = [
            item.widget()
            for index in range(page.card_grid.count())
            if (item := page.card_grid.itemAt(index)) is not None
        ]
        assert len(cards) == 10
        for card in cards:
            assert card is not None
            left = card.mapTo(stage.viewport(), QPoint(0, 0)).x()
            assert left >= 0
            assert left + card.width() <= stage.viewport().width()
        assert all(card is not None for card in cards)
        assert len({card.y() for card in cards if card is not None}) == rows
        if width == 940:
            assert stage.verticalScrollBar().maximum() > 0
        stage.verticalScrollBar().setValue(stage.verticalScrollBar().maximum())
        wait_for_queued_qt_turn()
        last = cards[-1]
        assert last is not None
        bottom = last.mapTo(stage.viewport(), last.rect().bottomRight()).y()
        assert bottom < stage.viewport().height()
    finally:
        page.show_failure(ModelFamilyId.SDXL, app_text("Unavailable"))
        host.close()
        destroy_qt_object(host)
