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

"""Verify mounted media wall scrolling, virtualization, and tooltips."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from qfluentwidgets import ScrollBar  # type: ignore[import-untyped]

from substitute.presentation.widgets.media_wall import (
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
    PickerJustifiedWallProfile,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter
from tests.support.execution import ImmediateTaskSubmitter
from tests.presentation.widgets.media_wall.support import (
    AssetRepository,
    CountingAssetRepository,
    MediaWallOwner,
    mouse_move_event,
    square_wall_item,
    thumbnail_asset,
    wait_for_preloader_idle,
    wall_item,
)


@pytest.fixture
def media_wall_owner() -> Generator[MediaWallOwner, None, None]:
    """Own every mounted scrolling surface."""

    owner = MediaWallOwner()
    yield owner
    owner.destroy_all()


def test_filtering_does_not_load_thumbnails(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Avoid thumbnail reads while replacing hidden wall items."""

    repository = CountingAssetRepository()
    view = media_wall_owner.create(asset_repository=repository)
    view.resize(400, 260)
    view.set_items((wall_item("one"), wall_item("two")))
    view.set_items((wall_item("one"),))

    assert repository.reads == 0
    assert len(view.items()) == 1


def test_wall_uses_row_appropriate_scroll_step(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Use a useful pixel step rather than Qt's tiny default."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.set_items(tuple(wall_item(str(index)) for index in range(20)))

    assert view.verticalScrollBar().singleStep() >= 72


def test_wall_uses_qfluent_scrollbar_chrome(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Synchronize visible QFluent scrollbar metrics to the wall range."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.show()
    view.set_items(tuple(wall_item(str(index)) for index in range(30)))
    fluent = view.findChild(ScrollBar)

    assert fluent is not None
    assert fluent.maximum() == view.verticalScrollBar().maximum()
    assert fluent.pageStep() == view.verticalScrollBar().pageStep()
    assert fluent.singleStep() == view.verticalScrollBar().singleStep()


def test_qfluent_scrollbar_value_tracks_wheel_and_partner(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Synchronize wheel and programmatic partner-scroll changes."""

    view = media_wall_owner.create()
    view.resize(400, 260)
    view.show()
    view.set_items(tuple(wall_item(str(index)) for index in range(30)))
    fluent = view.findChild(ScrollBar)
    assert fluent is not None
    assert view.verticalScrollBar().maximum() > 0
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(view.viewport().mapToGlobal(QPoint(10, 10))),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    view.wheelEvent(event)

    assert view.verticalScrollBar().value() == view.verticalScrollBar().singleStep()
    assert fluent.value() == view.verticalScrollBar().value()
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    assert fluent.value() == view.verticalScrollBar().maximum()


def test_wall_preloads_only_visible_and_overscan_rows(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Limit thumbnail requests to visible and overscan rows."""

    repository = AssetRepository(
        {str(index): thumbnail_asset(str(index), QColor("red")) for index in range(30)}
    )
    cache = MediaWallThumbnailCache()
    preloader = MediaWallThumbnailPreloader(
        cache=cache,
        asset_repository=repository,
        submitter=ImmediateTaskSubmitter(),
    )
    view = media_wall_owner.create(
        thumbnail_cache=cache,
        thumbnail_preloader=preloader,
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        ),
    )
    try:
        view.resize(300, 220)
        view.show()
        view.set_items(tuple(square_wall_item(str(index)) for index in range(30)))
        wait_for_preloader_idle(preloader)
        cache.clear()
        preloader.clear()
        repository.reads_by_key.clear()
        view.verticalScrollBar().setValue(500)
        wait_for_preloader_idle(preloader)

        assert set(repository.reads_by_key) == {str(index) for index in range(12, 27)}
    finally:
        preloader.shutdown()


def test_hit_testing_uses_scrolled_document_rows(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Resolve the correct document tile through a scrolled viewport."""

    view = media_wall_owner.create(
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        ),
    )
    view.resize(300, 220)
    view.setUpdatesEnabled(False)
    view.viewport().setUpdatesEnabled(False)
    view._fluent_vertical_scroll_bar.setUpdatesEnabled(False)
    view.show()
    view.set_items(tuple(square_wall_item(str(index)) for index in range(30)))
    view.verticalScrollBar().setValue(500)

    hit = view._item_at(QPoint(150, 50))

    assert hit is not None
    assert hit.item_id == "16"


def test_qfluent_tooltip_tracks_hovered_tile_path(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Route hovered tile text through the shared cursor tooltip filter."""

    view = media_wall_owner.create(
        profile=PickerJustifiedWallProfile(
            target_row_height=100,
            min_row_height=100,
            max_row_height=100,
            minimum_tile_width=80,
            gutter=0,
        )
    )
    view.resize(300, 220)
    view.show()
    view.set_items(
        (
            wall_item("one", tooltip="checkpoints/one.safetensors"),
            wall_item("two", tooltip="checkpoints/two.safetensors"),
        )
    )
    event = mouse_move_event(view, QPoint(10, 10))

    assert isinstance(view._tooltip_filter, FluentToolTipFilter)
    assert view._tooltip_filter.eventFilter(view.viewport(), event) is False
    assert view.toolTip() == "checkpoints/one.safetensors"
    assert view.tooltip_text_at(QPoint(100, 10)) == "checkpoints/two.safetensors"
    assert view.tooltip_text_at(QPoint(10, 150)) is None
