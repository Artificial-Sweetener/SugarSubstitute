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

"""Verify prompt reorder landing state and events."""

from __future__ import annotations


from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    prompt_chip_bubble_union_rect,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_events import (
    PromptReorderLandingEventPublisher,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderHeldShadowGeometry,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_state import (
    PromptReorderLandingStateOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)

from .support import (
    _LandingShadowLog,
    _request,
    _event_names,
)


def test_landing_state_owner_publishes_only_authoritative_transitions() -> None:
    """Landing state must be immutable, revisioned, and skip duplicate reasons."""

    owner = PromptReorderLandingStateOwner()
    initial = owner.publication

    owner.set_skip_reason("none")
    owner.record_missing_held_shadow()

    assert owner.publication is initial
    assert owner.counters.held_shadow_missing_count == 1

    held_rects = (QRectF(0.0, 0.0, 52.0, 14.0),)
    held = PromptReorderHeldShadowGeometry(
        chip_index=1,
        normalized_bubble_rects=held_rects,
        chrome_bounds=prompt_chip_bubble_union_rect(held_rects),
        hotspot_bounds=QRectF(0.0, 0.0, 62.0, 20.0),
        source="test",
    )
    assert owner.adopt_held_shadow(held) is True
    captured = owner.publication
    assert captured.revision == initial.revision + 1
    assert captured.held_shadow_geometry is held
    assert owner.adopt_held_shadow(held) is False
    assert owner.publication is captured

    owner.reset()

    assert owner.publication.revision == captured.revision + 1
    assert owner.publication.held_shadow_geometry is None
    assert owner.counters.held_shadow_capture_count == 0


def test_landing_event_publisher_owns_skip_event_classification() -> None:
    """Operational skip reasons must map to stable event names and context."""

    log = _LandingShadowLog()
    events = PromptReorderLandingEventPublisher(
        telemetry=PromptReorderTelemetry(),
        log_event=log.event,
        log_timing=log.timing,
    )
    request = _request()

    for reason in (
        "no_dragged_segment",
        "no_active_target",
        "no_preview_layout",
        "missing_authoritative_geometry",
    ):
        events.preview_skipped(request, reason)

    assert tuple(_event_names(log)) == (
        "landing_preview.skipped_no_dragged_segment",
        "landing_preview.skipped_no_active_target",
        "landing_preview.skipped_no_preview_layout",
        "landing_preview.skipped_no_geometry",
    )
    assert "dragged_segment_index" not in log.events[0][1]
    assert log.events[-1][1]["preview_visual_count"] == request.preview_visual_count
