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

"""Verify prompt reorder landing paint."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget

from .support import (
    _owners,
    _chip_view,
    _geometry,
    _placement,
    _request,
    _empty_capture,
    _event_names,
    _visual_style,
)


def test_drag_landing_preview_paint_state_uses_geometry() -> None:
    """Drag landing paint state should expose geometry and record preview context."""

    session, _resolution, paint, log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
    )

    result = paint.landing_preview_paint_state(
        request,
        visual_style=_visual_style(),
    )

    assert result.paint_state is not None
    assert result.paint_state.geometry is not None
    assert result.paint_state.visual is None
    assert result.paint_state.style.outline_only is True
    assert result.paint_state.style.opacity > 0.8
    assert session.publication.last_preview_geometry == result.paint_state.geometry
    assert session.publication.last_preview_visual is not None
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_chip_index == 1
    assert "landing_preview.paint" in {event for event, _context in log.timings}


def test_landing_paint_cache_reuses_only_exact_strong_input_identity() -> None:
    """Exact requests should reuse while equal replacement objects miss."""

    session, _resolution, paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
    )
    style = _visual_style()

    first = paint.landing_preview_paint_state(request, visual_style=style)
    ready = paint.landing_preview_paint_state(request, visual_style=style)
    reused = paint.landing_preview_paint_state(request, visual_style=style)
    replacement = paint.landing_preview_paint_state(
        replace(request, dragged_segment=_chip_view()),
        visual_style=style,
    )

    assert ready is not first
    assert reused is ready
    assert replacement is not ready
    assert paint.counters.paint_cache_hit_count == 1
    assert paint.counters.paint_cache_miss_count == 3


def test_pending_landing_shadow_paint_state_uses_held_visual() -> None:
    """Pending landing paint state should expose held-shadow visual fallback."""

    session, _resolution, paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
        landing_geometry=None,
        include_dragged_segment=False,
    )

    result = paint.landing_preview_paint_state(
        request,
        visual_style=_visual_style(),
    )

    assert result.paint_state is not None
    assert result.paint_state.geometry is None
    assert result.paint_state.visual is not None
    assert result.paint_state.style.outline_only is True
    assert result.paint_state.style.opacity < 0.6
    assert paint.counters.pending_shadow_fallback_count == 1
    assert paint.counters.pending_shadow_replaced_marker_count == 1


def test_missing_landing_inputs_return_empty_paint_state() -> None:
    """Landing paint construction should return no state without geometry or held metrics."""

    _session, _resolution, paint, _log = _owners()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)

    result = paint.landing_preview_paint_state(
        _request(
            target=target,
            placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
            landing_geometry=None,
            include_dragged_segment=False,
        ),
        visual_style=_visual_style(),
    )

    assert result.paint_state is None


def test_stale_landing_shadow_rejection_records_fallback_state() -> None:
    """A placement for another target must reject and expose marker fallback."""

    session, resolution, paint, log = _owners()
    active_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    stale_target = PromptLineDropTarget(row_index=1, insertion_index=2)
    request = _request(
        target=active_target,
        placement=_placement(
            stale_target,
            anchor=QRectF(100.0, 50.0, 8.0, 18.0),
        ),
    )

    accepted = resolution.landing_shadow_matches_active_target(
        request,
        _geometry(QRectF(100.0, 50.0, 52.0, 14.0)),
        emit_rejection=True,
    )

    assert accepted is False
    assert session.publication.last_rejected_target == active_target
    assert paint.counters.stale_shadow_rejected_count == 1
    assert tuple(_event_names(log))[-2:] == (
        "preview_shadow.rejected_stale_target",
        "preview_geometry.lightweight_marker_used",
    )
