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

"""Verify authoritative post-drop reorder diagnostic state and classification."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QPainterPath

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drop_actual_observation import (
    PromptReorderDropActualObservation,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drop_commit_diagnostics import (
    PromptReorderDropCommitDiagnostics,
    PromptReorderDropReleaseObservation,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_state import (
    PromptReorderLandingState,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometryId,
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets import (
    PromptReorderDropTargetVisual,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _RecordingTelemetry(PromptReorderTelemetry):
    """Record validated event publications for owner-level assertions."""

    def __init__(self) -> None:
        """Initialize telemetry with an in-memory event sink."""

        super().__init__()
        self.events: list[tuple[str, dict[str, object]]] = []

    def log_event(self, event: str, **context: object) -> None:
        """Record one event without using the process logger."""

        self.events.append((event, context))


def _visual(*, left: int) -> PromptChipVisual:
    """Build one stable chip visual at the supplied horizontal coordinate."""

    rect = QRect(left, 4, 40, 18)
    return PromptChipVisual(
        bubble_rects=(QRectF(rect),),
        fragment_union_rect=QRectF(rect),
        hotspot_rect=rect,
        slot_before=QPointF(rect.left(), rect.center().y()),
        slot_after=QPointF(rect.right(), rect.center().y()),
        marker_height=float(rect.height()),
    )


def _geometry(*, chip_index: int, left: int) -> PromptReorderChipGeometry:
    """Build one stable semantic chip geometry for diagnostic comparison."""

    rect = QRect(left, 4, 40, 18)
    return PromptReorderChipGeometry(
        geometry_id=PromptReorderChipGeometryId(
            chip_index=chip_index,
            visual_revision=3,
        ),
        chip_index=chip_index,
        source_start=0,
        source_end=4,
        rendered_start=0,
        rendered_end=4,
        visual_lines=(),
        hotspot_rect=rect,
        chrome_path=QPainterPath(),
        outline_bounds=QRectF(rect),
        slot_before=QPointF(rect.left(), rect.center().y()),
        slot_after=QPointF(rect.right(), rect.center().y()),
        marker_height=float(rect.height()),
    )


def _owner() -> tuple[
    PromptReorderDropCommitDiagnostics,
    _RecordingTelemetry,
    PromptReorderInteractionMetricsOwner,
]:
    """Build one diagnostics owner with inspectable event and metric authorities."""

    telemetry = _RecordingTelemetry()
    metrics = PromptReorderInteractionMetricsOwner()
    diagnostics = PromptReorderInteractionDiagnosticsOwner(
        telemetry=telemetry,
        metrics=metrics,
    )
    return (
        PromptReorderDropCommitDiagnostics(
            telemetry=telemetry,
            diagnostics=diagnostics,
        ),
        telemetry,
        metrics,
    )


def test_capture_publishes_one_immutable_drop_commit_state() -> None:
    """Retain and clear all post-drop fields through one authoritative state."""

    owner, _, _ = _owner()
    target = PromptLineDropTarget(row_index=1, insertion_index=2)
    shadow_visual = _visual(left=10)
    shadow_geometry = _geometry(chip_index=3, left=10)

    owner.capture(
        landing=PromptReorderLandingState(
            last_preview_visual=shadow_visual,
            last_preview_geometry=shadow_geometry,
        ),
        target=target,
        geometry=PromptReorderInteractionGeometryState(),
        segment_index=3,
        gesture_id=11,
        event_id=12,
    )

    assert owner.state.shadow_visual is shadow_visual
    assert owner.state.shadow_geometry is shadow_geometry
    assert owner.state.target == target
    assert owner.state.segment_index == 3
    assert owner.state.gesture_id == 11
    assert owner.state.event_id == 12

    owner.clear()

    assert owner.state.segment_index is None
    assert owner.state.shadow_visual is None
    assert owner.state.target is None


def test_release_observation_logs_one_complete_structural_snapshot() -> None:
    """Publish release diagnostics from explicit immutable observations."""

    owner, telemetry, _ = _owner()
    target = PromptLineDropTarget(row_index=1, insertion_index=2)
    visual = _visual(left=10)
    geometry = _geometry(chip_index=3, left=10)

    owner.log_release(
        PromptReorderDropReleaseObservation(
            dragged_segment_index=3,
            ending_target=target,
            shadow_visual=visual,
            shadow_geometry=geometry,
            current_preview_visual=visual,
            current_preview_geometry=geometry,
            target_visuals=(
                PromptReorderDropTargetVisual(
                    target=target,
                    hit_rect=QRectF(8.0, 2.0, 44.0, 22.0),
                ),
            ),
            active_placement=None,
            has_preview_layout=True,
            last_landing_preview_event_id=7,
            ordered_segment_indices=(1, 3, 2),
            gesture_id=11,
            event_id=12,
        )
    )

    event, context = telemetry.events[-1]
    assert event == "drop_commit.release_snapshot"
    assert context["gesture_id"] == 11
    assert context["event_id"] == 12
    assert context["dragged_segment_index"] == 3
    assert context["ordered_indices"] == "1,3,2"
    assert context["has_current_preview_geometry"] is True


def test_actual_geometry_uses_retained_identity_and_classifies_mismatch() -> None:
    """Use captured gesture identity and report a displaced post-drop chip."""

    owner, telemetry, metrics = _owner()
    target = PromptLineDropTarget(row_index=1, insertion_index=2)
    owner.capture(
        landing=PromptReorderLandingState(
            last_preview_visual=_visual(left=10),
            last_preview_geometry=_geometry(chip_index=3, left=10),
        ),
        target=target,
        geometry=PromptReorderInteractionGeometryState(),
        segment_index=3,
        gesture_id=11,
        event_id=12,
    )

    owner.log_actual(
        PromptReorderDropActualObservation(
            checkpoint="surface_sync",
            segment_index=3,
            actual_visual=_visual(left=40),
            actual_geometry=_geometry(chip_index=3, left=40),
            chip_rect=QRectF(40.0, 4.0, 40.0, 18.0),
            preview_mode_active=True,
            has_preview_snapshot=True,
            has_base_drag_snapshot=False,
            ordered_segment_indices=(1, 3, 2),
            gesture_id=None,
            event_id=None,
        )
    )

    actual_event = next(
        context
        for event, context in telemetry.events
        if event == "drop_commit.actual_geometry"
    )
    assert actual_event["gesture_id"] == 11
    assert actual_event["event_id"] == 12
    assert actual_event["actual_order_index"] == 1
    anomaly_events = [
        event for event, _ in telemetry.events if event.startswith("anomaly.")
    ]
    assert anomaly_events == [
        "anomaly.chip_geometry_commit_mismatch",
        "anomaly.drop_commit_shadow_actual_mismatch",
    ]
    assert metrics.snapshot().anomaly_count == 2


def test_actual_observation_prefers_preview_visual_and_live_geometry() -> None:
    """Resolve visible preview chrome while retaining live projection geometry."""

    live_visual = _visual(left=10)
    preview_visual = _visual(left=40)
    live_geometry = _geometry(chip_index=3, left=10)
    geometry_snapshot = PromptReorderChipGeometrySnapshot(
        geometries_by_chip_index={3: live_geometry},
        ordered_chip_indices=(3,),
        visual_line_count=1,
        layout_width=200.0,
        content_height=24.0,
        scroll_offset=0.0,
    )

    observation = PromptReorderDropActualObservation.from_publications(
        checkpoint="owner_test",
        segment_index=3,
        live_visuals={3: live_visual},
        preview_visuals={3: preview_visual},
        live_chip_geometry=geometry_snapshot,
        chip_rect=None,
        preview_mode_active=True,
        geometry=PromptReorderInteractionGeometryState(
            ordered_segment_indices=(3,),
        ),
        gesture_id=7,
        event_id=8,
    )

    assert observation.actual_visual is preview_visual
    assert observation.actual_geometry is live_geometry
    assert observation.ordered_segment_indices == (3,)
