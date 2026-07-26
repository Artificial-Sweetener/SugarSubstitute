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

"""Own post-drop reorder geometry state and diagnostic classification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
)

from ..projection.observability import reorder_drag_rect_context
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    chip_geometry_context,
)
from ..projection.reorder_drop_targets import PromptReorderDropTargetVisual
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    placement_geometry_context,
)
from .chip_visuals import PromptChipVisual
from .reorder_drop_actual_observation import PromptReorderDropActualObservation
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_landing_state import PromptReorderLandingState
from .reorder_telemetry import PromptReorderTelemetry

_SHADOW_ACTUAL_MISMATCH_X = 8.0
_SHADOW_ACTUAL_MISMATCH_Y = 8.0


@dataclass(frozen=True, slots=True)
class PromptReorderDropCommitState:
    """Publish immutable release geometry retained until surface synchronization."""

    shadow_visual: PromptChipVisual | None = None
    shadow_geometry: PromptReorderChipGeometry | None = None
    target: PromptReorderDropTarget | None = None
    placement: PromptReorderPlacementGeometry | None = None
    segment_index: int | None = None
    gesture_id: int | None = None
    event_id: int | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderDropReleaseObservation:
    """Describe projection and landing state observed at pointer release."""

    dragged_segment_index: int
    ending_target: PromptReorderDropTarget | None
    shadow_visual: PromptChipVisual | None
    shadow_geometry: PromptReorderChipGeometry | None
    current_preview_visual: PromptChipVisual | None
    current_preview_geometry: PromptReorderChipGeometry | None
    target_visuals: tuple[PromptReorderDropTargetVisual, ...]
    active_placement: PromptReorderPlacementGeometry | None
    has_preview_layout: bool
    last_landing_preview_event_id: int | None
    ordered_segment_indices: tuple[int, ...]
    gesture_id: int | None
    event_id: int | None

    @classmethod
    def from_publications(
        cls,
        *,
        dragged_segment_index: int,
        ending_target: PromptReorderDropTarget | None,
        landing: PromptReorderLandingState,
        preview_visuals: Mapping[int, PromptChipVisual],
        geometry: PromptReorderInteractionGeometryState,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderDropReleaseObservation:
        """Capture one release observation from immutable owner publications."""

        preview_geometry = geometry.preview_chip_geometry_snapshot
        return cls(
            dragged_segment_index=dragged_segment_index,
            ending_target=ending_target,
            shadow_visual=landing.last_preview_visual,
            shadow_geometry=landing.last_preview_geometry,
            current_preview_visual=preview_visuals.get(dragged_segment_index),
            current_preview_geometry=(
                None
                if preview_geometry is None
                else preview_geometry.geometries_by_chip_index.get(
                    dragged_segment_index
                )
            ),
            target_visuals=geometry.drop_target_visuals,
            active_placement=geometry.active_placement,
            has_preview_layout=geometry.preview_layout_view is not None,
            last_landing_preview_event_id=landing.last_preview_event_id,
            ordered_segment_indices=geometry.ordered_segment_indices,
            gesture_id=gesture_id,
            event_id=event_id,
        )


class PromptReorderDropCommitDiagnostics:
    """Retain one committed landing and classify its republished geometry."""

    def __init__(
        self,
        *,
        telemetry: PromptReorderTelemetry,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
    ) -> None:
        """Bind prompt-safe logging owners without retaining overlay collaborators."""

        self._telemetry = telemetry
        self._diagnostics = diagnostics
        self._state = PromptReorderDropCommitState()

    @property
    def state(self) -> PromptReorderDropCommitState:
        """Return the immutable release geometry awaiting surface synchronization."""

        return self._state

    def capture(
        self,
        *,
        landing: PromptReorderLandingState,
        target: PromptReorderDropTarget | None,
        geometry: PromptReorderInteractionGeometryState,
        segment_index: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> None:
        """Retain one committed landing until the actual surface geometry is ready."""

        self._state = PromptReorderDropCommitState(
            shadow_visual=landing.last_preview_visual,
            shadow_geometry=landing.last_preview_geometry,
            target=target,
            placement=geometry.active_placement,
            segment_index=segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )

    def clear(self) -> None:
        """Discard any retained post-drop observation."""

        self._state = PromptReorderDropCommitState()

    def log_release(self, observation: PromptReorderDropReleaseObservation) -> None:
        """Log the shadow, target, and preview state observed at pointer release."""

        target_visual = next(
            (
                visual
                for visual in observation.target_visuals
                if visual.target == observation.ending_target
            ),
            None,
        )
        context: dict[str, object] = {
            "dragged_segment_index": observation.dragged_segment_index,
            "has_shadow_visual": observation.shadow_visual is not None,
            "has_shadow_geometry": observation.shadow_geometry is not None,
            "has_current_preview_visual": observation.current_preview_visual
            is not None,
            "has_current_preview_geometry": (
                observation.current_preview_geometry is not None
            ),
            "has_preview_layout": observation.has_preview_layout,
            "last_landing_preview_event_id": (
                observation.last_landing_preview_event_id
            ),
            "ordered_indices": ",".join(
                str(index) for index in observation.ordered_segment_indices
            ),
            **self._telemetry.target_context(
                observation.ending_target,
                prefix="ending_target",
            ),
            **placement_geometry_context(
                observation.active_placement,
                prefix="active_placement",
            ),
        }
        if target_visual is not None:
            context.update(
                self._telemetry.target_visual_context(target_visual, prefix="target")
            )
        if observation.shadow_visual is not None:
            context.update(
                self._telemetry.visual_context(
                    observation.shadow_visual,
                    prefix="shadow",
                )
            )
        if observation.shadow_geometry is not None:
            context.update(
                chip_geometry_context(
                    observation.shadow_geometry,
                    prefix="shadow_geometry",
                )
            )
        if observation.current_preview_visual is not None:
            context.update(
                self._telemetry.visual_context(
                    observation.current_preview_visual,
                    prefix="preview_actual",
                )
            )
        if observation.current_preview_geometry is not None:
            context.update(
                chip_geometry_context(
                    observation.current_preview_geometry,
                    prefix="preview_actual_geometry",
                )
            )
        if (
            observation.shadow_visual is not None
            and observation.current_preview_visual is not None
        ):
            context.update(
                self._telemetry.visual_delta_context(
                    observation.shadow_visual,
                    observation.current_preview_visual,
                    prefix="shadow_to_preview_actual",
                )
            )
        self._diagnostics.log_event(
            "drop_commit.release_snapshot",
            gesture_id=observation.gesture_id,
            event_id=observation.event_id,
            **context,
        )

    def log_actual(self, observation: PromptReorderDropActualObservation) -> None:
        """Log and classify actual geometry republished after a committed drop."""

        state = self._state
        try:
            actual_order_index = observation.ordered_segment_indices.index(
                observation.segment_index
            )
        except ValueError:
            actual_order_index = None
        context: dict[str, object] = {
            "checkpoint": observation.checkpoint,
            "segment_index": observation.segment_index,
            "actual_order_index": actual_order_index,
            "has_shadow_visual": state.shadow_visual is not None,
            "has_shadow_geometry": state.shadow_geometry is not None,
            "has_actual_visual": observation.actual_visual is not None,
            "has_actual_geometry": observation.actual_geometry is not None,
            "has_chip": observation.chip_rect is not None,
            "preview_mode_active": observation.preview_mode_active,
            "has_preview_snapshot": observation.has_preview_snapshot,
            "has_base_drag_snapshot": observation.has_base_drag_snapshot,
            "ordered_indices": ",".join(
                str(index) for index in observation.ordered_segment_indices
            ),
            **self._telemetry.target_context(state.target, prefix="commit_target"),
            **placement_geometry_context(
                state.placement,
                prefix="commit_placement",
            ),
        }
        if state.shadow_visual is not None:
            context.update(
                self._telemetry.visual_context(state.shadow_visual, prefix="shadow")
            )
        if state.shadow_geometry is not None:
            context.update(
                chip_geometry_context(
                    state.shadow_geometry,
                    prefix="shadow_geometry",
                )
            )
        if observation.actual_visual is not None:
            context.update(
                self._telemetry.visual_context(
                    observation.actual_visual,
                    prefix="actual",
                )
            )
        if observation.actual_geometry is not None:
            context.update(
                chip_geometry_context(
                    observation.actual_geometry,
                    prefix="actual_geometry",
                )
            )
        if observation.chip_rect is not None:
            context.update(
                reorder_drag_rect_context(observation.chip_rect, prefix="chip")
            )
        if state.shadow_visual is not None and observation.actual_visual is not None:
            context.update(
                self._telemetry.visual_delta_context(
                    state.shadow_visual,
                    observation.actual_visual,
                    prefix="shadow_to_actual",
                )
            )
        gesture_id = observation.gesture_id or state.gesture_id
        event_id = observation.event_id or state.event_id
        self._diagnostics.log_event(
            "drop_commit.actual_geometry",
            gesture_id=gesture_id,
            event_id=event_id,
            **context,
        )
        if state.shadow_visual is None and state.target is not None:
            self._diagnostics.log_anomaly(
                "anomaly.drop_commit_missing_shadow",
                checkpoint=observation.checkpoint,
                segment_index=observation.segment_index,
                commit_gesture_id=state.gesture_id,
                commit_event_id=state.event_id,
                **self._telemetry.target_context(
                    state.target,
                    prefix="commit_target",
                ),
            )
        if observation.actual_visual is None:
            self._diagnostics.log_anomaly(
                "anomaly.drop_commit_missing_actual_visual",
                checkpoint=observation.checkpoint,
                segment_index=observation.segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=state.gesture_id,
                commit_event_id=state.event_id,
            )
            return
        if observation.actual_geometry is None:
            self._diagnostics.log_anomaly(
                "anomaly.chip_geometry_commit_missing",
                checkpoint=observation.checkpoint,
                segment_index=observation.segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=state.gesture_id,
                commit_event_id=state.event_id,
            )
            return
        if state.shadow_geometry is not None and _chip_geometries_mismatch(
            state.shadow_geometry,
            observation.actual_geometry,
        ):
            self._diagnostics.log_anomaly(
                "anomaly.chip_geometry_commit_mismatch",
                checkpoint=observation.checkpoint,
                segment_index=observation.segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=state.gesture_id,
                commit_event_id=state.event_id,
                **self._telemetry.target_context(
                    state.target,
                    prefix="commit_target",
                ),
                **chip_geometry_context(
                    state.shadow_geometry,
                    prefix="shadow_geometry",
                ),
                **chip_geometry_context(
                    observation.actual_geometry,
                    prefix="actual_geometry",
                ),
            )
        if state.shadow_visual is not None and _visuals_mismatch(
            state.shadow_visual,
            observation.actual_visual,
        ):
            self._diagnostics.log_anomaly(
                "anomaly.drop_commit_shadow_actual_mismatch",
                checkpoint=observation.checkpoint,
                segment_index=observation.segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=state.gesture_id,
                commit_event_id=state.event_id,
                **self._telemetry.target_context(
                    state.target,
                    prefix="commit_target",
                ),
                **self._telemetry.visual_delta_context(
                    state.shadow_visual,
                    observation.actual_visual,
                    prefix="shadow_to_actual",
                ),
                **self._telemetry.visual_context(
                    state.shadow_visual,
                    prefix="shadow",
                ),
                **self._telemetry.visual_context(
                    observation.actual_visual,
                    prefix="actual",
                ),
            )


def _visuals_mismatch(
    expected_visual: PromptChipVisual,
    actual_visual: PromptChipVisual,
) -> bool:
    """Return whether visual anchors disagree enough to explain a bad landing."""

    return _rects_mismatch(
        QRectF(expected_visual.hotspot_rect),
        QRectF(actual_visual.hotspot_rect),
    )


def _chip_geometries_mismatch(
    expected_geometry: PromptReorderChipGeometry,
    actual_geometry: PromptReorderChipGeometry,
) -> bool:
    """Return whether semantic chip geometry disagrees after commit."""

    return expected_geometry.chip_index != actual_geometry.chip_index or (
        _rects_mismatch(
            QRectF(expected_geometry.hotspot_rect),
            QRectF(actual_geometry.hotspot_rect),
        )
    )


def _rects_mismatch(expected_rect: QRectF, actual_rect: QRectF) -> bool:
    """Return whether two rect anchors exceed the landing tolerance."""

    return (
        abs(actual_rect.center().x() - expected_rect.center().x())
        > _SHADOW_ACTUAL_MISMATCH_X
        or abs(actual_rect.center().y() - expected_rect.center().y())
        > _SHADOW_ACTUAL_MISMATCH_Y
        or abs(actual_rect.left() - expected_rect.left()) > _SHADOW_ACTUAL_MISMATCH_X
        or abs(actual_rect.top() - expected_rect.top()) > _SHADOW_ACTUAL_MISMATCH_Y
    )


__all__ = [
    "PromptReorderDropCommitDiagnostics",
    "PromptReorderDropCommitState",
    "PromptReorderDropReleaseObservation",
]
