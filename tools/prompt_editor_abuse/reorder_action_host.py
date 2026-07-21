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

from PySide6.QtCore import QEventLoop, QPoint, QPointF, QRect, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import PromptLineDropTarget

from .action_driver import PromptAbuseActionHost
from .models import PromptAbuseAction


class PromptReorderAbuseActionHost(PromptAbuseActionHost):
    """Own one pointer drag session through production reorder chips."""

    def __init__(self) -> None:
        """Initialize an inactive pointer drag session."""

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
        if action.kind == "reorder_drag_threshold" and (
            overlay is None or overlay.dragged_segment_index() is None
        ):
            mismatches.append("reorder_drag_threshold:dragged_segment_index=None")
        if action.kind == "reorder_drag_release" and (
            overlay is not None and overlay.dragged_segment_index() is not None
        ):
            mismatches.append(
                "reorder_drag_release:"
                f"dragged_segment_index={overlay.dragged_segment_index()}"
            )
        if overlay is not None:
            mismatches.extend(_reorder_render_state_mismatches(overlay))
        return exact and not mismatches, ";".join(mismatches) or None

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
    layout_view = prompt_overlay._base_drag_layout_view
    placement_snapshot = prompt_overlay._placement_snapshot
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
        expected_indices = set(overlay._preview_visuals_by_index)
        chips = render_state.preview_chips
    else:
        expected_indices = set(overlay._visuals_by_index)
        chips = render_state.live_chips
    dragged_segment_index = render_state.dragged_segment_index
    if dragged_segment_index is not None:
        expected_indices.discard(dragged_segment_index)
    surface_chrome = surface._reorder_surface_chrome_snapshot
    surface_indices = (
        set()
        if surface_chrome is None
        else {chip.segment_index for chip in surface_chrome.chips}
    )
    rendered_indices = {chip.segment_index for chip in chips} | surface_indices
    mismatches: list[str] = []
    if child_hotspot_count:
        mismatches.append(
            f"reorder_pointer_surface:child_hotspots={child_hotspot_count}:expected=0"
        )
    missing_indices = tuple(sorted(expected_indices - rendered_indices))
    if missing_indices:
        animation_indices = tuple(
            sorted(overlay._animation_presenter.paint_rect_overrides())
        )
        held_indices = tuple(
            sorted(overlay._held_chip_presenter.paint_rect_overrides())
        )
        snapshot_indices = tuple(sorted(overlay._preview_visual_snapshots_by_index))
        animation_counters = overlay._animation_presenter.counters()
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
            content_free_indices & set(overlay._last_suppressed_chip_snapshots_by_index)
        )
    )
    if unsafe_suppressed_indices:
        mismatches.append(
            "reorder_render_state:content_free_suppressed="
            f"{unsafe_suppressed_indices!r}"
        )
    active_layout = (
        surface._reorder_preview_projection.preview_layout
        if render_state.preview_active
        else surface._layout
    )
    unresolved_fragments = (
        ()
        if active_layout is None
        else tuple(
            (
                fragment.run_id,
                fragment.token_id,
                getattr(fragment, "text", ""),
                fragment.projection_start,
            )
            for line in active_layout._snapshot.lines
            for fragment in line.fragments
            if active_layout.effective_run_for_paint(fragment.run_id) is None
            or (
                fragment.token_id is not None
                and active_layout.effective_token_for_paint(fragment.token_id) is None
            )
        )
    )
    if unresolved_fragments:
        mismatches.append(
            "reorder_projection_semantics:unresolved="
            f"{unresolved_fragments[:8]!r}:count={len(unresolved_fragments)}"
        )
    return tuple(mismatches)


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
