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

"""Verify typed reorder interaction diagnostic ownership."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderGestureSummaryContext,
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderLandingShadowCounters,
)


class _Telemetry:
    """Capture diagnostic emissions without using process logging."""

    def __init__(self) -> None:
        """Initialize empty event, timing, and slow-path captures."""

        self.events: list[tuple[str, dict[str, object]]] = []
        self.timings: list[tuple[str, dict[str, object]]] = []
        self.slow_paths: list[tuple[str, dict[str, object]]] = []

    def log_event(self, event: str, **context: object) -> None:
        """Capture one structural event."""

        self.events.append((event, context))

    def log_timing(
        self,
        event: str,
        *,
        started_at: float,
        **context: object,
    ) -> float:
        """Capture one timing event and return a deterministic duration."""

        self.timings.append((event, {"started_at": started_at, **context}))
        return 4.25

    def log_slow_path_if_needed(
        self,
        event: str,
        *,
        elapsed_ms: float,
        threshold_ms: float,
        gesture_id: int | None,
        event_id: int | None,
        **context: object,
    ) -> None:
        """Capture one correlated slow-path request."""

        self.slow_paths.append(
            (
                event,
                {
                    "elapsed_ms": elapsed_ms,
                    "threshold_ms": threshold_ms,
                    "gesture_id": gesture_id,
                    "event_id": event_id,
                    **context,
                },
            )
        )


def test_diagnostics_correlate_events_and_own_metric_classification() -> None:
    """Anomalies and pointer violations should share owner identities."""

    telemetry = _Telemetry()
    metrics = PromptReorderInteractionMetricsOwner()
    metrics.begin_gesture(19)
    diagnostics = PromptReorderInteractionDiagnosticsOwner(
        telemetry=telemetry,
        metrics=metrics,
    )

    diagnostics.log_anomaly("visual.mismatch", chip_index=2)
    diagnostics.log_expected_geometry("visual.expected_offset", chip_index=3)
    diagnostics.record_pointer_unexpected_work("paint_request")
    metrics.begin_pointer_move()
    diagnostics.record_pointer_unexpected_work("paint_request", reason="test")
    metrics.leave_pointer_loop()
    elapsed_ms = diagnostics.log_timing("phase", started_at=1.0, count=2)
    diagnostics.log_slow_path_if_needed(
        "slow.drag_move",
        elapsed_ms=20.0,
        threshold_ms=16.0,
    )

    snapshot = metrics.snapshot()
    assert snapshot.anomaly_count == 1
    assert snapshot.expected_diagnostic_count == 1
    assert snapshot.pointer_unexpected_work_count == 1
    assert snapshot.pointer_paint_request_count == 1
    assert elapsed_ms == 4.25
    assert [event for event, _ in telemetry.events] == [
        "visual.mismatch",
        "visual.expected_offset",
        "pointer_loop.unexpected_work",
    ]
    assert telemetry.events[0][1]["gesture_id"] == 19
    assert telemetry.events[-1][1]["reason"] == "test"
    assert telemetry.slow_paths[0][1]["gesture_id"] == 19
    assert telemetry.slow_paths[0][1]["event_id"] == 1


def test_diagnostics_build_one_summary_from_immutable_owner_evidence() -> None:
    """Gesture summaries should merge metrics and collaborator counters once."""

    telemetry = _Telemetry()
    metrics = PromptReorderInteractionMetricsOwner()
    metrics.begin_gesture(8)
    metrics.begin_pointer_move()
    metrics.leave_pointer_loop()
    metrics.record_pointer_move_outcome(elapsed_ms=3.5, target_changed=True)
    diagnostics = PromptReorderInteractionDiagnosticsOwner(
        telemetry=telemetry,
        metrics=metrics,
    )

    diagnostics.log_gesture_summary(
        PromptReorderGestureSummaryContext(
            outcome="end",
            chip_geometry_count=2,
            preview_chip_geometry_count=1,
            expected_chip_count=3,
            placement_geometry_count=4,
            landing_counters=PromptReorderLandingShadowCounters(
                anomaly_count=2,
                expected_diagnostic_count=3,
            ),
            owner_counters={"cache_hit_count": 5},
        )
    )

    event, context = telemetry.events[-1]
    assert event == "gesture_summary"
    assert context["gesture_id"] == 8
    assert context["move_count"] == 1
    assert context["target_change_count"] == 1
    assert context["chip_geometry_missing_count"] == 1
    assert context["placement_geometry_count"] == 4
    assert context["anomaly_count"] == 2
    assert context["diagnostic_expected_offset_count"] == 3
    assert context["cache_hit_count"] == 5
    assert context["max_drag_move_ms"] == "3.500"
