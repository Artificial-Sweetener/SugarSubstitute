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

"""Tests for prompt projection fill-band and viewport metric behavior."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionFillBandCache,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    delay_projection_update_scheduler,
    flush_semantic_refresh,
    new_projection_surface,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_projection_surface_exposes_visible_prompt_fill_band_rects(
    widgets: list[QWidget],
) -> None:
    """Prompt fill band geometry should match projection viewport coordinates."""

    box = show_prompt_editor(
        widgets,
        text="quality\n**one\nwide shot\n**two\nclose portrait",
        width=360,
    )
    surface = surface_for(box)
    fill_rects = surface.visible_prompt_fill_band_rects()

    assert fill_rects
    assert {fill_rect.band_index for fill_rect in fill_rects} == {0, 1, 2}
    assert all(fill_rect.rect.left() == 0 for fill_rect in fill_rects)
    assert all(
        fill_rect.rect.width() == surface.viewport().width() for fill_rect in fill_rects
    )


def test_projection_surface_prompt_fill_band_rects_follow_scroll_offset(
    widgets: list[QWidget],
) -> None:
    """Prompt fill band geometry should be reported in visible scrolled coordinates."""

    box = show_prompt_editor(
        widgets,
        text="**one\nsetup\n**two\n"
        + "\n".join(f"scene line {index}" for index in range(12)),
        width=360,
    )
    surface = surface_for(box)
    scrollbar = surface.verticalScrollBar()
    before_scroll = surface.visible_prompt_fill_band_rects()

    scrollbar.setValue(scrollbar.singleStep() * 2)
    process_events(ensure_qapp())

    after_scroll = surface.visible_prompt_fill_band_rects()
    assert before_scroll
    assert after_scroll
    assert after_scroll[0].rect.top() < before_scroll[0].rect.top()


def test_projection_surface_first_scene_band_shifts_after_global_prompt(
    widgets: list[QWidget],
) -> None:
    """A global preamble should occupy band zero before the first scene."""

    with_global = show_prompt_editor(
        widgets,
        text="quality\n**one\nwide shot",
        width=360,
    )
    without_global = show_prompt_editor(
        widgets,
        text="**one\nwide shot",
        width=360,
    )

    with_global_bands = {
        fill_rect.band_index
        for fill_rect in surface_for(with_global).visible_prompt_fill_band_rects()
    }
    without_global_bands = {
        fill_rect.band_index
        for fill_rect in surface_for(without_global).visible_prompt_fill_band_rects()
    }

    assert with_global_bands == {0, 1}
    assert without_global_bands == {0}


def test_projection_surface_content_height_uses_committed_metric_during_pending_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passive height reads should not force scheduled projection work while typing."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    committed_height = surface.content_height()
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    assert surface.content_height() == pytest.approx(committed_height)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0


def test_projection_surface_reuses_committed_width_for_transient_invalid_viewport(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transient 1px viewport widths should not become projection wrap widths."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    committed_metrics = surface._projection_freshness_controller.committed_metrics  # noqa: SLF001
    assert committed_metrics is not None
    committed_width = committed_metrics.viewport_width

    monkeypatch.setattr(surface.viewport(), "width", lambda: 1)

    assert surface._layout_width_for_projection_rebuild() == pytest.approx(  # noqa: SLF001
        committed_width
    )


def test_projection_surface_uses_parent_width_for_hidden_uncommitted_viewport(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hidden staged editors should not lay out long prompts at tiny viewport widths."""

    host = QWidget()
    host.resize(520, 180)
    surface = new_projection_surface(parent=host)
    surface.resize(79, 120)
    widgets.extend([host, surface])

    monkeypatch.setattr(surface.viewport(), "width", lambda: 79)
    surface._projection_freshness_controller.committed_metrics = None  # noqa: SLF001

    assert surface._projection_freshness_controller.committed_metrics is None  # noqa: SLF001
    assert surface._layout_width_for_projection_rebuild() == pytest.approx(  # noqa: SLF001
        520
    )


def test_projection_surface_uses_realistic_fallback_for_hidden_unparented_viewport(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unparented hidden editors should still avoid pathological prompt wrapping."""

    surface = new_projection_surface()
    surface.resize(79, 120)
    widgets.append(surface)

    monkeypatch.setattr(surface.viewport(), "width", lambda: 79)
    surface._projection_freshness_controller.committed_metrics = None  # noqa: SLF001

    assert surface._projection_freshness_controller.committed_metrics is None  # noqa: SLF001
    assert surface._layout_width_for_projection_rebuild() == pytest.approx(  # noqa: SLF001
        760.0
    )


def test_projection_surface_fill_bands_use_committed_layout_during_pending_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passive fill-band reads should not force scheduled projection work."""

    box = show_prompt_editor(
        widgets,
        text="quality\n**one\nwide shot\n",
        width=360,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    committed_bands = surface.visible_prompt_fill_band_rects()
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    stale_bands = surface.visible_prompt_fill_band_rects()

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0
    assert tuple(band.band_index for band in stale_bands) == tuple(
        band.band_index for band in committed_bands
    )


def test_projection_surface_fill_bands_reuse_cache_for_same_view_state(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated passive fill-band reads should not walk layout geometry again."""

    box = show_prompt_editor(
        widgets,
        text="quality\n**one\nwide shot\n",
        width=360,
    )
    surface = surface_for(box)
    original_row_rects = surface._layout.source_range_row_rects  # noqa: SLF001
    row_rect_call_count = 0

    def count_row_rects(
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Record layout geometry walks while preserving production behavior."""

        nonlocal row_rect_call_count
        row_rect_call_count += 1
        return original_row_rects(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    monkeypatch.setattr(surface._layout, "source_range_row_rects", count_row_rects)  # noqa: SLF001

    first = surface.visible_prompt_fill_band_rects()
    first_call_count = row_rect_call_count
    second = surface.visible_prompt_fill_band_rects()

    assert first
    assert second == first
    assert row_rect_call_count == first_call_count


def test_projection_surface_fill_band_cache_key_tracks_view_state(
    widgets: list[QWidget],
) -> None:
    """Fill-band cache identity should change with passive view metrics."""

    box = show_prompt_editor(
        widgets,
        text="quality\n**one\nwide shot\n",
        width=360,
    )
    surface = surface_for(box)

    first_key = surface._fill_band_cache_key()  # noqa: SLF001
    cached_bands = PromptProjectionFillBandCache(key=first_key, rects=())

    assert surface._fill_band_cache_matches(cached_bands, first_key) is True  # noqa: SLF001

    surface.set_source_line_content_left_inset(24.0)
    inset_key = surface._fill_band_cache_key()  # noqa: SLF001

    assert inset_key != first_key
    assert inset_key.content_left_inset == 24.0
    assert surface._fill_band_cache_matches(cached_bands, inset_key) is False  # noqa: SLF001
