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

"""Dispatch measured pointer reorder actions through production chip hotspots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import QEventLoop, QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor.reorder.projection import (
    domain_state_from_view,
    domain_target_from_view,
)
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.domain.prompt.reorder.models import (
    PromptLineDropTarget as DomainPromptLineDropTarget,
)
from substitute.domain.prompt.reorder.mutations import (
    apply_drop_target_to_state,
    apply_line_drop_target_to_state,
)

from .action_driver import PromptAbuseActionHost
from .models import PromptAbuseAction


class PromptReorderAbuseActionHost(PromptAbuseActionHost):
    """Own one pointer drag session through production reorder chips."""

    def __init__(self) -> None:
        """Initialize an inactive pointer drag session."""

        super().__init__()
        self._source_chip: _OverlayChipTarget | None = None
        self._start = QPoint()
        self._target = QPoint()
        self._target_segment_index: int | None = None

    def reorder_drag_press(self, editor: object, value: str) -> None:
        """Press one segment chip without conflating press and drag startup."""

        source_text, separator, target_text = value.partition(":")
        if separator != ":":
            raise ValueError(f"Invalid reorder drag descriptor {value!r}.")
        prompt_editor = cast(Any, editor)
        overlay = cast(QWidget, prompt_editor._segment_overlay)
        source_index = _resolved_segment_index(source_text, overlay)
        target_index = _resolved_segment_index(target_text, overlay)
        source_chip = overlay_chip(overlay, source_index)
        self._source_chip = source_chip
        self._start = source_chip.rect.center()
        QTest.mousePress(
            overlay,
            Qt.MouseButton.LeftButton,
            pos=self._start,
            delay=0,
        )
        target_chip = overlay_chip(overlay, target_index)
        self._target = _target_point(overlay, target_chip)
        self._target_segment_index = target_index

    def reorder_drag_threshold(self, editor: object) -> None:
        """Cross the native threshold once and require a production drag gesture."""

        del editor
        source_chip = self._require_active_drag()
        direction = 1 if self._target.x() >= self._start.x() else -1
        threshold_position = QPoint(
            self._start.x() + direction * (QApplication.startDragDistance() + 1),
            self._start.y(),
        )
        QTest.mouseMove(source_chip.overlay, threshold_position, delay=0)
        target_segment_index = self._target_segment_index
        if target_segment_index is None:
            raise RuntimeError("Reorder drag threshold has no destination segment.")
        semantic_target = _semantic_drop_target(
            source_chip.overlay,
            target_segment_index=target_segment_index,
        )
        self._target = (
            semantic_target.point
            if semantic_target is not None
            else _target_point(
                source_chip.overlay,
                overlay_chip(source_chip.overlay, target_segment_index),
            )
        )

    def reorder_drag_move(self, editor: object, value: str) -> None:
        """Move the pressed chip to one normalized point along its drag path."""

        del editor
        source_chip = self._require_active_drag()
        progress = float(value)
        if not 0.0 <= progress <= 1.0:
            raise ValueError(f"Reorder drag progress is outside [0, 1]: {progress}.")
        target_segment_index = self._target_segment_index
        if target_segment_index is None:
            raise RuntimeError("Reorder drag move has no destination segment.")
        semantic_target = _semantic_drop_target(
            source_chip.overlay,
            target_segment_index=target_segment_index,
        )
        if semantic_target is not None:
            self._target = semantic_target.point
        position = QPoint(
            round(self._start.x() + (self._target.x() - self._start.x()) * progress),
            round(self._start.y() + (self._target.y() - self._start.y()) * progress),
        )
        QTest.mouseMove(source_chip.overlay, position, delay=0)

    def reorder_drag_sweep(self, editor: object) -> None:
        """Drive the real mouse path through every currently published placement."""

        del editor
        source_chip = self._require_active_drag()
        overlay = cast(Any, source_chip.overlay)
        placement_snapshot = overlay._geometry.state.placement_snapshot
        if placement_snapshot is None or not placement_snapshot.placements:
            raise RuntimeError("Reorder drag sweep has no prepared placements.")
        for placement in placement_snapshot.placements:
            QTest.mouseMove(
                source_chip.overlay,
                _pointer_point_for_placement(overlay, placement.hit_rect.center()),
                delay=0,
            )
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
        for placement in reversed(placement_snapshot.placements):
            QTest.mouseMove(
                source_chip.overlay,
                _pointer_point_for_placement(overlay, placement.hit_rect.center()),
                delay=0,
            )
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
            mismatches = tuple(
                mismatch
                for mismatch in (
                    _reorder_sweep_target_mismatch(overlay, placement),
                    _invalid_reorder_active_target_mismatch(overlay),
                    _reorder_active_preview_mismatch(overlay),
                    _reorder_landing_shadow_mismatch(overlay),
                )
                if mismatch is not None
            )
            if mismatches:
                raise RuntimeError(";".join(mismatches))

    def reorder_drag_release(self, editor: object) -> None:
        """Release through the grabbed hotspot after the target move was delivered."""

        del editor
        source_chip = self._require_active_drag()
        target_segment_index = self._target_segment_index
        if target_segment_index is None:
            raise RuntimeError("Reorder drag release has no destination segment.")
        semantic_target = _semantic_drop_target(
            source_chip.overlay,
            target_segment_index=target_segment_index,
        )
        if semantic_target is not None:
            self._target = semantic_target.point
            active_target = cast(
                Any, source_chip.overlay
            )._gesture.state.active_drop_target
            if active_target != semantic_target.target:
                QTest.mouseMove(source_chip.overlay, self._target, delay=0)
        QTest.mouseRelease(
            source_chip.overlay,
            Qt.MouseButton.LeftButton,
            pos=self._target,
            delay=0,
        )
        self._source_chip = None
        self._target_segment_index = None

    def reorder_drag_autoscroll(self, editor: object) -> None:
        """Hold the active pointer at the lower edge until scrolling begins."""

        source_chip = self._require_active_drag()
        prompt_editor = cast(Any, editor)
        overlay = cast(QWidget, prompt_editor._segment_overlay)
        scrollbar = prompt_editor.verticalScrollBar()
        initial_value = int(scrollbar.value())
        edge_global = overlay.mapToGlobal(
            QPoint(max(2, overlay.width() // 2), max(2, overlay.height() - 2))
        )
        QTest.mouseMove(
            source_chip.overlay,
            source_chip.overlay.mapFromGlobal(edge_global),
            delay=0,
        )
        _wait_until(lambda: int(scrollbar.value()) > initial_value)

    def reorder_drag_cancel(self, editor: object, target: QWidget) -> None:
        """Cancel the complete reorder mode through the real Escape key route."""

        self._require_active_drag()
        QTest.keyClick(target, Qt.Key.Key_Escape, delay=0)
        self._source_chip = None
        self._target_segment_index = None
        if cast(Any, editor)._segment_overlay is not None:
            raise RuntimeError("Reorder drag Escape did not close reorder mode.")

    def capture_feature_checkpoint(
        self,
        editor: object,
        action: PromptAbuseAction,
    ) -> tuple[bool, str | None]:
        """Require the measured threshold action to activate the real gesture."""

        exact, mismatch = super().capture_feature_checkpoint(editor, action)
        overlay = cast(Any, editor)._segment_overlay
        mismatches = [item for item in (mismatch,) if item is not None]
        dragged_segment_index = (
            None
            if overlay is None
            else overlay.pointer_reorder_state().dragged_segment_index
        )
        if action.kind == "reorder_drag_threshold" and (
            overlay is None or dragged_segment_index is None
        ):
            mismatches.append("reorder_drag_threshold:dragged_segment_index=None")
        if action.kind == "reorder_drag_release" and (
            overlay is not None and dragged_segment_index is not None
        ):
            mismatches.append(
                f"reorder_drag_release:dragged_segment_index={dragged_segment_index}"
            )
        if overlay is not None:
            placement_mismatch = _invalid_reorder_placement_mismatch(overlay)
            if placement_mismatch is not None:
                mismatches.append(placement_mismatch)
            target_mismatch = self._destination_target_mismatch(overlay, action)
            if target_mismatch is not None:
                mismatches.append(target_mismatch)
            mismatches.extend(_reorder_render_state_mismatches(overlay))
            landing_mismatch = _reorder_landing_shadow_mismatch(overlay)
            if landing_mismatch is not None:
                mismatches.append(landing_mismatch)
        return exact and not mismatches, ";".join(mismatches) or None

    def _destination_target_mismatch(
        self,
        overlay: QWidget,
        action: PromptAbuseAction,
    ) -> str | None:
        """Require the terminal pointer move to reach its semantic destination."""

        if action.kind != "reorder_drag_move" or float(action.value) < 1.0:
            return None
        target_segment_index = self._target_segment_index
        if target_segment_index is None:
            return "reorder_destination:target_segment_index=None"
        semantic_target = _semantic_drop_target(
            overlay,
            target_segment_index=target_segment_index,
        )
        active_target = cast(Any, overlay)._gesture.state.active_drop_target
        if semantic_target is None:
            return (
                "reorder_destination:"
                f"segment={target_segment_index}:semantic_target=None:"
                f"active={active_target!r}"
            )
        if active_target != semantic_target.target:
            return (
                "reorder_destination:"
                f"segment={target_segment_index}:"
                f"expected={semantic_target.target!r}:active={active_target!r}"
            )
        return None

    def _require_active_drag(self) -> _OverlayChipTarget:
        """Return the active source chip or reject an invalid action sequence."""

        if self._source_chip is None:
            raise RuntimeError("Reorder drag action requires an active press.")
        return self._source_chip


@dataclass(frozen=True, slots=True)
class _OverlayChipTarget:
    """Identify one logical chip region on the production overlay surface."""

    overlay: QWidget
    segment_index: int
    rect: QRect


@dataclass(frozen=True, slots=True)
class _SemanticDropTarget:
    """Pair one typed production drop target with its current pointer point."""

    target: PromptLineDropTarget
    point: QPoint


def overlay_chip(overlay: QWidget, segment_index: int) -> _OverlayChipTarget:
    """Return one production reorder pointer target by stable segment index."""

    rects = cast(Any, overlay).pointer_region_rects()
    rect = rects.get(segment_index)
    if rect is None:
        raise RuntimeError(f"Missing reorder segment chip {segment_index}.")
    return _OverlayChipTarget(overlay, segment_index, QRect(rect))


def _target_point(overlay: QWidget, target_chip: _OverlayChipTarget) -> QPoint:
    """Return one overlay-local destination point for a resolved logical chip."""

    global_target = overlay.mapToGlobal(
        QPoint(
            target_chip.rect.left() + 4,
            max(target_chip.rect.top() + 4, target_chip.rect.center().y()),
        )
    )
    return overlay.mapFromGlobal(global_target)


def _semantic_drop_target(
    overlay: QWidget,
    *,
    target_segment_index: int,
) -> _SemanticDropTarget | None:
    """Return the current lane and pointer point before one logical segment."""

    prompt_overlay = cast(Any, overlay)
    layout_view = prompt_overlay.preview_build_facts.snapshot().base_drag_layout_view
    placement_snapshot = prompt_overlay._geometry.state.placement_snapshot
    if layout_view is None or placement_snapshot is None:
        return None
    target: PromptLineDropTarget | None = None
    for row in layout_view.rows:
        try:
            insertion_index = row.chip_indices.index(target_segment_index)
        except ValueError:
            continue
        target = PromptLineDropTarget(
            row_index=row.row_index,
            insertion_index=insertion_index,
        )
        break
    if target is None:
        return None
    placement = placement_snapshot.placement_for_target(target)
    if placement is None:
        return None
    drag_state = prompt_overlay._gesture.state
    size = drag_state.drag_intent_size
    grab_offset = drag_state.drag_grab_offset
    if size is None or size.isEmpty() or grab_offset is None:
        return None
    center = placement.hit_rect.center()
    local_pointer = (
        center
        + grab_offset
        - QPointF(
            size.width() / 2.0,
            size.height() / 2.0,
        )
    )
    return _SemanticDropTarget(
        target=target,
        point=QPoint(round(local_pointer.x()), round(local_pointer.y())),
    )


def _pointer_point_for_placement(overlay: Any, center: QPointF) -> QPoint:
    """Return the pointer position that centers the held chip on a placement."""

    drag_state = overlay._gesture.state
    size = drag_state.drag_intent_size
    grab_offset = drag_state.drag_grab_offset
    if size is None or size.isEmpty() or grab_offset is None:
        raise RuntimeError("Reorder drag sweep has no captured drag intent geometry.")
    local_pointer = (
        center
        + grab_offset
        - QPointF(
            size.width() / 2.0,
            size.height() / 2.0,
        )
    )
    return QPoint(round(local_pointer.x()), round(local_pointer.y()))


def _resolved_segment_index(value: str, overlay: QWidget) -> int:
    """Resolve an exact or viewport-relative segment descriptor."""

    if value != "last-visible":
        return int(value)
    pointer_region_rects = cast(
        dict[int, QRect], cast(Any, overlay).pointer_region_rects()
    )
    indices = tuple(pointer_region_rects)
    if not indices:
        raise RuntimeError("Reorder overlay has no visible segment chips.")
    return max(indices)


def _reorder_render_state_mismatches(overlay: Any) -> tuple[str, ...]:
    """Return missing or content-free visible reorder paint states."""

    if not overlay.isVisible():
        return ()
    child_hotspot_count = len(overlay.findChildren(QWidget, "segmentChip"))
    render_state = overlay._view.render_state
    surface = cast(Any, overlay)._editor._surface
    if render_state.preview_active:
        expected_indices = set(overlay._preview_visual_owner.visuals_by_index)
        chips = render_state.preview_chips
    else:
        expected_indices = set(overlay._live_visual_owner.visuals_by_index)
        chips = render_state.live_chips
    dragged_segment_index = render_state.dragged_segment_index
    if dragged_segment_index is not None:
        expected_indices.discard(dragged_segment_index)
    surface_visual_state = surface._reorder_surface_visual_state.state
    surface_chrome = surface_visual_state.chrome_snapshot
    surface_indices = (
        set()
        if surface_chrome is None
        else {chip.segment_index for chip in surface_chrome.chips}
    )
    rendered_indices = {chip.segment_index for chip in chips} | surface_indices
    mismatches: list[str] = []
    unsafe_indices = overlay._render_publication.publication.unsafe_transient_indices
    if unsafe_indices:
        mismatches.append(f"reorder_render_state:unsafe_transient={unsafe_indices!r}")
    if child_hotspot_count:
        mismatches.append(
            f"reorder_pointer_surface:child_hotspots={child_hotspot_count}:expected=0"
        )
    missing_indices = tuple(sorted(expected_indices - rendered_indices))
    if missing_indices:
        animation_publication = overlay._animation_presentation.publication
        animation_indices = tuple(
            sorted(animation_publication.displacement_rects_by_index)
        )
        held_indices = tuple(sorted(animation_publication.held_rects_by_index))
        snapshot_indices = tuple(
            sorted(overlay._preview_paint_snapshots.snapshots_by_index)
        )
        animation_counters = overlay._animation_presentation.counters()
        mismatches.append(
            "reorder_render_state:"
            f"missing={missing_indices!r}:"
            f"animation={animation_indices!r}:"
            f"held={held_indices!r}:"
            f"snapshots={snapshot_indices!r}:"
            f"animation_counters={animation_counters!r}"
        )
    content_free_indices = {
        chip.segment_index for chip in chips if not chip.owns_projection_text
    }
    unsafe_suppressed_indices = tuple(
        sorted(
            content_free_indices
            & set(surface_visual_state.suppression_snapshots_by_index)
        )
    )
    if unsafe_suppressed_indices:
        mismatches.append(
            "reorder_render_state:content_free_suppressed="
            f"{unsafe_suppressed_indices!r}"
        )
    active_frame = (
        surface._reorder_preview_projection.preview_frame
        if render_state.preview_active
        else surface._layout.frame
    )
    unresolved_fragments = (
        ()
        if active_frame is None
        else tuple(
            (
                fragment.run_id,
                fragment.token_id,
                getattr(fragment, "text", ""),
                fragment.projection_start,
            )
            for line in active_frame.output.snapshot.lines
            for fragment in line.fragments
            if active_frame.paint_input.effective_run(fragment.run_id) is None
            or (
                fragment.token_id is not None
                and active_frame.paint_input.effective_token(fragment.token_id) is None
            )
        )
    )
    if unresolved_fragments:
        mismatches.append(
            "reorder_projection_semantics:unresolved="
            f"{unresolved_fragments[:8]!r}:count={len(unresolved_fragments)}"
        )
    return tuple(mismatches)


def _reorder_landing_shadow_mismatch(overlay: Any) -> str | None:
    """Require visible chip-shaped feedback for every active drag target."""

    gesture = overlay._gesture.state
    if gesture.dragged_segment_index is None or gesture.active_drop_target is None:
        return None
    active_placement = overlay._geometry.state.active_placement
    landing_preview = overlay._view.render_state.landing_preview
    if (
        active_placement is not None
        and active_placement.target == gesture.active_drop_target
        and landing_preview is not None
        and (landing_preview.geometry is not None or landing_preview.visual is not None)
    ):
        return None
    landing = overlay._landing_visual
    return (
        "reorder_landing_shadow:"
        f"target={gesture.active_drop_target!r}:"
        f"placement={None if active_placement is None else active_placement.target!r}:"
        f"paint={landing_preview is not None}:"
        f"geometry={
            False if landing_preview is None else landing_preview.geometry is not None
        }:"
        f"visual={
            False if landing_preview is None else landing_preview.visual is not None
        }:"
        f"skip={landing.state.publication.last_preview_skip_reason}:"
        f"counters={landing.counters()!r}"
    )


def _invalid_reorder_placement_mismatch(overlay: Any) -> str | None:
    """Require every published line placement to be valid for the drag-base state."""

    geometry_state = overlay._geometry.state
    placement_snapshot = geometry_state.placement_snapshot
    base_state_view = geometry_state.base_drag_reorder_state
    if placement_snapshot is None or base_state_view is None:
        return None
    base_state = domain_state_from_view(base_state_view)
    dragged_segment_index = overlay._gesture.state.dragged_segment_index
    if dragged_segment_index is None:
        return None
    for placement in placement_snapshot.placements:
        target = placement.target
        if not isinstance(target, PromptLineDropTarget):
            continue
        try:
            apply_line_drop_target_to_state(
                base_state,
                dragged_segment_index=dragged_segment_index,
                target=DomainPromptLineDropTarget(
                    row_index=target.row_index,
                    insertion_index=target.insertion_index,
                ),
            )
        except ValueError as error:
            return (
                "reorder_invalid_placement:"
                f"target={target!r}:"
                f"ordered={base_state.ordered_segment_indices!r}:"
                f"partitions={base_state.partition_index_by_segment_index!r}:"
                f"slots={base_state.separator_slots!r}:"
                f"error={error}"
            )
    return None


def _invalid_reorder_active_target_mismatch(overlay: Any) -> str | None:
    """Require the active line target to mutate the authoritative drag-base state."""

    geometry_state = overlay._geometry.state
    target = overlay._gesture.state.active_drop_target
    base_state_view = geometry_state.base_drag_reorder_state
    dragged_segment_index = overlay._gesture.state.dragged_segment_index
    if (
        not isinstance(target, PromptLineDropTarget)
        or base_state_view is None
        or dragged_segment_index is None
    ):
        return None
    try:
        apply_line_drop_target_to_state(
            domain_state_from_view(base_state_view),
            dragged_segment_index=dragged_segment_index,
            target=DomainPromptLineDropTarget(
                row_index=target.row_index,
                insertion_index=target.insertion_index,
            ),
        )
    except ValueError as error:
        return f"reorder_invalid_active_target:target={target!r}:error={error}"
    return None


def _reorder_sweep_target_mismatch(
    overlay: Any,
    intended_placement: Any,
) -> str | None:
    """Require a placement-centered pointer move to select that semantic target."""

    active_target = overlay._gesture.state.active_drop_target
    active_placement = overlay._geometry.state.active_placement
    if (
        active_target == intended_placement.target
        and active_placement is not None
        and active_placement.target == intended_placement.target
    ):
        return None
    return (
        "reorder_sweep_target:"
        f"expected={intended_placement.target!r}:"
        f"expected_id={intended_placement.placement_id!r}:"
        f"expected_hit={intended_placement.hit_rect!r}:"
        f"expected_anchor={intended_placement.insertion_anchor_rect!r}:"
        f"active={active_target!r}:"
        f"placement={None if active_placement is None else active_placement.target!r}:"
        f"placement_id={
            None if active_placement is None else active_placement.placement_id!r
        }:"
        f"placement_hit={
            None if active_placement is None else active_placement.hit_rect!r
        }:"
        f"placement_anchor={
            None
            if active_placement is None
            else active_placement.insertion_anchor_rect!r
        }"
    )


def _reorder_active_preview_mismatch(overlay: Any) -> str | None:
    """Require the painted preview state to equal the active domain mutation."""

    geometry_state = overlay._geometry.state
    target = overlay._gesture.state.active_drop_target
    base_state_view = geometry_state.base_drag_reorder_state
    preview_state_view = geometry_state.preview_reorder_state
    dragged_segment_index = overlay._gesture.state.dragged_segment_index
    if (
        target is None
        or base_state_view is None
        or preview_state_view is None
        or dragged_segment_index is None
    ):
        return None
    try:
        expected_state = apply_drop_target_to_state(
            domain_state_from_view(base_state_view),
            dragged_segment_index=dragged_segment_index,
            target=domain_target_from_view(target),
        )
    except ValueError:
        return None
    actual_state = domain_state_from_view(preview_state_view)
    if actual_state == expected_state:
        return None
    return (
        "reorder_active_preview:"
        f"target={target!r}:"
        f"expected_order={expected_state.ordered_segment_indices!r}:"
        f"actual_order={actual_state.ordered_segment_indices!r}:"
        f"expected_slots={expected_state.separator_slots!r}:"
        f"actual_slots={actual_state.separator_slots!r}"
    )


def _wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 250) -> None:
    """Wait on Qt timer work until an observable drag condition becomes true."""

    remaining_ms = timeout_ms
    while not predicate() and remaining_ms > 0:
        loop = QEventLoop()
        interval_ms = min(5, remaining_ms)
        QTimer.singleShot(interval_ms, loop.quit)
        loop.exec()
        remaining_ms -= interval_ms
    if not predicate():
        raise RuntimeError("Reorder drag autoscroll did not advance before timeout.")


__all__ = ["PromptReorderAbuseActionHost", "overlay_chip"]
