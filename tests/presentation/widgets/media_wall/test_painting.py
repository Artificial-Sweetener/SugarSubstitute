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

"""Verify media wall tile painting, theme borders, and marquee policy."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from PySide6.QtCore import QPoint, QRect

from substitute.presentation.widgets.media_wall import MediaWallItem
from substitute.presentation.widgets.media_wall.media_wall_marquee import (
    TitleMarqueeState,
    resolve_title_marquee_state,
)
from substitute.presentation.widgets.media_wall.media_wall_painter import (
    title_and_subtitle_rects,
)
from substitute.presentation.widgets.media_wall.media_wall_style import (
    media_wall_current_border,
    media_wall_hover_border,
)
from tests.presentation.widgets.media_wall.support import (
    MediaWallOwner,
    ensure_qapp,
    find_pixel_different_from_background,
    find_pixel_matching_background,
    paint_wall_item_image,
    pixel_color_difference,
    rect_images_differ,
)


@pytest.fixture
def media_wall_owner() -> Generator[MediaWallOwner, None, None]:
    """Own walls used for offscreen paint contracts."""

    owner = MediaWallOwner()
    yield owner
    owner.destroy_all()


def test_tile_style_uses_accent_current_border() -> None:
    """Derive valid current and hover borders from QFluent theme state."""

    current = media_wall_current_border()
    hover = media_wall_hover_border()

    assert current.isValid()
    assert hover.isValid()
    assert current.alpha() > hover.alpha()
    assert (current.red(), current.green(), current.blue()) != (255, 255, 255)


def test_tile_paints_subtitle_without_hover(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Keep tile subtitles visible without hover or selection."""

    ensure_qapp()
    widget = media_wall_owner.create()
    widget.resize(180, 240)
    rect = widget.viewport().rect()
    with_subtitle = MediaWallItem(
        item_id="one",
        title="Page Name",
        subtitle="Version Name",
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )
    without_subtitle = MediaWallItem(
        item_id="one",
        title="Page Name",
        subtitle=None,
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )

    first = paint_wall_item_image(widget, with_subtitle, rect)
    second = paint_wall_item_image(widget, without_subtitle, rect)
    _title_rect, subtitle_rect = title_and_subtitle_rects(
        rect,
        widget.fontMetrics(),
        subtitle_visible=True,
    )

    assert rect_images_differ(first, second, subtitle_rect)


def test_marquee_edge_fade_masks_text_without_touching_background(
    media_wall_owner: MediaWallOwner,
) -> None:
    """Apply marquee fades to title glyphs without changing tile pixels."""

    ensure_qapp()
    widget = media_wall_owner.create()
    widget.resize(180, 240)
    rect = widget.viewport().rect()
    item = MediaWallItem(
        item_id="one",
        title="A Very Long Page Name That Needs Marquee",
        subtitle="Version Name",
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )
    background_item = MediaWallItem(
        item_id="one",
        title="",
        subtitle="Version Name",
        aspect_ratio=0.72,
        thumbnail_variants=(),
        payload="one",
    )
    background = paint_wall_item_image(widget, background_item, rect)
    unmasked = paint_wall_item_image(
        widget,
        item,
        rect,
        title_marquee_state=TitleMarqueeState(
            phase="scroll",
            offset=12.0,
            show_left_fade=False,
            show_right_fade=False,
        ),
    )
    masked = paint_wall_item_image(
        widget,
        item,
        rect,
        title_marquee_state=TitleMarqueeState(
            phase="scroll",
            offset=12.0,
            show_left_fade=True,
            show_right_fade=True,
        ),
    )
    title_rect, subtitle_rect = title_and_subtitle_rects(
        rect,
        widget.fontMetrics(),
        subtitle_visible=True,
    )
    left_fade_rect = QRect(
        title_rect.left(),
        title_rect.top(),
        18,
        title_rect.height(),
    )
    text_point = find_pixel_different_from_background(
        unmasked,
        background,
        left_fade_rect,
    )
    background_point = find_pixel_matching_background(
        unmasked,
        background,
        left_fade_rect,
    )
    subtitle_left_edge = QPoint(
        subtitle_rect.left() + 2,
        subtitle_rect.center().y(),
    )

    assert pixel_color_difference(masked, background, text_point) < (
        pixel_color_difference(unmasked, background, text_point)
    )
    assert masked.pixelColor(background_point) == background.pixelColor(
        background_point
    )
    assert masked.pixelColor(subtitle_left_edge) == background.pixelColor(
        subtitle_left_edge
    )


def test_title_marquee_holds_scrolls_and_holds_end() -> None:
    """Keep overflowing titles readable at both ends of their marquee cycle."""

    start = resolve_title_marquee_state(elapsed_ms=0, overflow_width=120)
    scrolling = resolve_title_marquee_state(elapsed_ms=1400, overflow_width=120)
    end = resolve_title_marquee_state(elapsed_ms=3700, overflow_width=120)

    assert start.phase == "start"
    assert start.show_right_fade
    assert scrolling.phase == "scroll"
    assert scrolling.offset > 0
    assert scrolling.show_left_fade
    assert scrolling.show_right_fade
    assert end.phase == "end"
    assert end.show_left_fade
