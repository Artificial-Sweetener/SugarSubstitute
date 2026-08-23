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

"""Verify prompt reorder landing session capture."""

from __future__ import annotations


from PySide6.QtCore import QPointF, QRect, QRectF, QSize

from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)

from .support import (
    _owners,
    _geometry,
    _empty_capture,
    _event_names,
)


def test_landing_shadow_capture_prefers_live_chip_geometry() -> None:
    """Held-shadow capture should use projection-owned live geometry first."""

    session, _resolution, paint, log = _owners()

    session.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(QRectF(8.0, 9.0, 44.0, 15.0)),
            chip_size=QSize(90, 30),
        )
    )

    held = session.publication.held_shadow_geometry
    assert held is not None
    assert held.source == "live_chip_geometry"
    assert held.outline_size.width() == 44.0
    assert paint.counters.held_shadow_capture_count == 1
    assert "preview_shadow.held_size_captured" in set(_event_names(log))


def test_landing_shadow_capture_uses_fallback_sources() -> None:
    """Held-shadow capture should fall back through prepared visual/widget sources."""

    session, _resolution, _paint, _log = _owners()

    session.capture_held_shadow(
        _empty_capture(
            live_visual=PromptChipVisual(
                bubble_rects=(QRectF(2.0, 3.0, 30.0, 12.0),),
                fragment_union_rect=QRectF(2.0, 3.0, 30.0, 12.0),
                hotspot_rect=QRect(0, 0, 40, 20),
                slot_before=QPointF(2.0, 9.0),
                slot_after=QPointF(32.0, 9.0),
                marker_height=12.0,
            )
        )
    )

    held = session.publication.held_shadow_geometry
    assert held is not None
    assert held.source == "live_chip_visual"
    assert not held.low_confidence

    session.reset_drag_state()
    session.capture_held_shadow(_empty_capture(chip_size=QSize(22, 13)))

    held = session.publication.held_shadow_geometry
    assert held is not None
    assert held.source == "chip_widget"
    assert held.low_confidence


def test_landing_shadow_missing_geometry_records_missing_without_exception() -> None:
    """Missing held-shadow inputs should be diagnostic-only and non-throwing."""

    session, _resolution, paint, log = _owners()

    session.capture_held_shadow(_empty_capture())

    assert session.publication.held_shadow_geometry is None
    assert paint.counters.held_shadow_missing_count == 1
    assert "preview_shadow.held_size_missing" in set(_event_names(log))
