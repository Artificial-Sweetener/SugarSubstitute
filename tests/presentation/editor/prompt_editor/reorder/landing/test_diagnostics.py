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

"""Verify prompt reorder landing diagnostics."""

from __future__ import annotations


from PySide6.QtCore import QPointF, QRect, QRectF

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
    prompt_chip_bubble_union_rect,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_diagnostics import (
    PromptReorderLandingDiagnostics,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderHeldShadowGeometry,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)

from .support import (
    _LandingShadowLog,
    _owners,
    _geometry,
    _placement,
    _request,
    _empty_capture,
    _event_names,
)


def test_pending_shadow_diagnostics_compare_wrapped_and_authoritative_shapes() -> None:
    """Pending chrome must retain mismatch events and diagnostic accounting."""

    session, resolution, paint, log = _owners()
    session.capture_held_shadow(
        _empty_capture(
            live_geometry=_geometry(
                QRectF(8.0, 9.0, 52.0, 14.0),
                QRectF(8.0, 31.0, 38.0, 14.0),
            )
        )
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=0)
    request = _request(
        target=target,
        placement=_placement(target, anchor=QRectF(100.0, 50.0, 8.0, 18.0)),
        landing_geometry=_geometry(QRectF(100.0, 50.0, 52.0, 14.0)),
    )

    visual = resolution.pending_shadow_preview_visual(request, reason="characterize")

    assert visual is not None
    event_names = tuple(_event_names(log))
    assert "preview_shadow.pending_authoritative_delta" in event_names
    assert "diagnostic.pending_authoritative_shadow_bubble_count_delta" in event_names
    assert paint.counters.expected_diagnostic_count == 1


def test_landing_diagnostics_own_classification_counters_and_reset() -> None:
    """The diagnostic owner must classify and reset without owner state."""

    log = _LandingShadowLog()
    diagnostics = PromptReorderLandingDiagnostics(
        telemetry=PromptReorderTelemetry(),
        log_event=log.event,
    )
    held_rects = (
        QRectF(0.0, 0.0, 52.0, 14.0),
        QRectF(0.0, 22.0, 38.0, 14.0),
    )
    held = PromptReorderHeldShadowGeometry(
        chip_index=1,
        normalized_bubble_rects=held_rects,
        chrome_bounds=prompt_chip_bubble_union_rect(held_rects),
        hotspot_bounds=QRectF(0.0, 0.0, 62.0, 42.0),
        source="test",
    )
    pending_visual = PromptChipVisual(
        bubble_rects=held_rects,
        fragment_union_rect=prompt_chip_bubble_union_rect(held_rects),
        hotspot_rect=QRect(0, 0, 62, 42),
        slot_before=QPointF(0.0, 7.0),
        slot_after=QPointF(38.0, 29.0),
        marker_height=14.0,
    )

    diagnostics.pending_shadow_shape(
        _request(landing_geometry=_geometry(QRectF(0.0, 0.0, 52.0, 14.0))),
        pending_visual,
        held,
        reason="owner-contract",
    )

    assert diagnostics.counters.expected_diagnostic_count == 1
    assert diagnostics.counters.anomaly_count == 1
    diagnostics.reset()
    assert diagnostics.counters.expected_diagnostic_count == 0
    assert diagnostics.counters.anomaly_count == 0
