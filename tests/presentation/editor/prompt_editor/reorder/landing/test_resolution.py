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

"""Verify prompt reorder landing resolution."""

from __future__ import annotations


from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget

from .support import (
    _owners,
    _geometry,
    _placement,
    _request,
    _empty_capture,
)


def test_pending_landing_shadow_preserves_held_wrapped_rows() -> None:
    """Pending fallback should translate held bubble rows without collapsing them."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(
                QRectF(8.0, 9.0, 52.0, 14.0),
                QRectF(8.0, 31.0, 38.0, 14.0),
            )
        )
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(120.0, 50.0, 8.0, 18.0))

    visual = resolution.pending_shadow_preview_visual(
        _request(target=target, placement=placement),
        reason="test",
    )

    held = session.publication.held_shadow_geometry
    assert visual is not None
    assert held is not None
    assert len(visual.bubble_rects) == len(held.normalized_bubble_rects)
    assert max(rect.height() for rect in visual.bubble_rects) == max(
        rect.height() for rect in held.normalized_bubble_rects
    )


def test_missing_preview_geometry_uses_placement_owned_held_shadow() -> None:
    """Missing preview geometry should still yield a placement-owned shadow."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0))

    result = resolution.landing_preview_for_active_target(
        _request(target=target, placement=placement, landing_geometry=None)
    )

    assert result.geometry is not None
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_bounds == QRectF(
        result.geometry.hotspot_rect
    )
    held = session.publication.held_shadow_geometry
    assert held is not None
    assert result.geometry.outline_bounds.width() == held.outline_size.width()


def test_authoritative_preview_geometry_wins_over_placement_owned_shadow() -> None:
    """Landing preview must use the same preview geometry that chips settle to."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    placement = _placement(target, anchor=QRectF(140.0, 80.0, 8.0, 18.0))
    preview_geometry = _geometry(QRectF(24.0, 22.0, 52.0, 14.0))

    result = resolution.landing_preview_for_active_target(
        _request(
            target=target,
            placement=placement,
            landing_geometry=preview_geometry,
        )
    )

    assert result.geometry is preview_geometry
    assert result.active_placement is not None
    assert result.active_placement.expected_landing_bounds == QRectF(
        preview_geometry.hotspot_rect
    )


def test_landing_shadow_updates_when_target_placement_changes() -> None:
    """Target changes should derive landing geometry from the new placement."""

    session, resolution, _paint, _log = _owners()
    session.capture_held_shadow(
        _empty_capture(live_geometry=_geometry(QRectF(8.0, 9.0, 52.0, 14.0)))
    )
    first_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    second_target = PromptLineDropTarget(row_index=0, insertion_index=2)
    first_result = resolution.landing_preview_for_active_target(
        _request(
            target=first_target,
            placement=_placement(first_target, anchor=QRectF(40.0, 40.0, 8.0, 18.0)),
        )
    )
    second_result = resolution.landing_preview_for_active_target(
        _request(
            target=second_target,
            placement=_placement(
                second_target,
                anchor=QRectF(150.0, 40.0, 8.0, 18.0),
            ),
        )
    )

    assert first_result.geometry is not None
    assert second_result.geometry is not None
    assert second_result.geometry.hotspot_rect != first_result.geometry.hotspot_rect
    assert second_result.active_placement is not None
    assert second_result.active_placement.target == second_target
