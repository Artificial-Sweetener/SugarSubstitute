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

"""Select reachable pointer samples for every reorder abuse placement."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QEventLoop, QPoint, QPointF, QRect, QRectF, QSizeF, QTimer

from substitute.presentation.editor.prompt_editor.projection.reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
    placement_for_drag_rect,
)

type ReorderSweepSnapshotSupplier = Callable[[], PromptReorderPlacementSnapshot | None]
type ReorderSweepConditionWaiter = Callable[[Callable[[], bool]], bool]


def wait_for_reorder_sweep_pointer_plan(
    *,
    snapshot_supplier: ReorderSweepSnapshotSupplier,
    drag_intent_size: QSizeF | None,
    drag_grab_offset: QPointF | None,
    pointer_bounds: QRect,
    wait: ReorderSweepConditionWaiter | None = None,
) -> tuple[PromptReorderPlacementSnapshot, tuple[QPoint, ...]]:
    """Wait until every published placement has a real pointer coordinate."""

    if (
        drag_intent_size is None
        or drag_intent_size.isEmpty()
        or drag_grab_offset is None
    ):
        raise RuntimeError("Reorder drag sweep has no captured drag intent geometry.")
    plan: tuple[PromptReorderPlacementSnapshot, tuple[QPoint, ...]] | None = None
    last_error: RuntimeError | None = None

    def capture_reachable_plan() -> bool:
        """Capture one coherent topology without retaining a provisional frame."""

        nonlocal last_error, plan
        snapshot = snapshot_supplier()
        if snapshot is None or not snapshot.placements:
            return False
        try:
            pointers = tuple(
                pointer_for_reorder_sweep_placement(
                    snapshot,
                    placement,
                    drag_intent_size=drag_intent_size,
                    drag_grab_offset=drag_grab_offset,
                    pointer_bounds=pointer_bounds,
                    active_placement_id=None,
                )
                for placement in snapshot.placements
            )
        except RuntimeError as error:
            last_error = error
            return False
        plan = (snapshot, pointers)
        return True

    condition_waiter = wait or _wait_for_condition
    if condition_waiter(capture_reachable_plan):
        assert plan is not None
        return plan
    if last_error is not None:
        raise RuntimeError(
            "Reorder drag sweep placements did not become coherently reachable."
        ) from last_error
    raise RuntimeError("Reorder drag sweep has no prepared placements.")


def pointer_for_reorder_sweep_placement(
    snapshot: PromptReorderPlacementSnapshot,
    placement: PromptReorderPlacementGeometry,
    *,
    drag_intent_size: QSizeF,
    drag_grab_offset: QPointF,
    pointer_bounds: QRect,
    active_placement_id: PromptReorderPlacementId | None,
) -> QPoint:
    """Find a native pointer coordinate resolving to the intended placement.

    Hit rectangles may overlap. Their centers are not guaranteed to select the
    intended target because the production resolver preserves an active overlap.
    """

    if drag_intent_size.isEmpty():
        raise RuntimeError("Reorder drag sweep has no captured drag intent geometry.")
    competing_rects = tuple(
        candidate.hit_rect
        for candidate in snapshot.placements
        if candidate.placement_id != placement.placement_id
    )
    x_samples = _axis_samples(
        placement.hit_rect.left(),
        placement.hit_rect.right(),
        (rect.left() for rect in competing_rects),
        (rect.right() for rect in competing_rects),
    )
    y_samples = _axis_samples(
        placement.hit_rect.top(),
        placement.hit_rect.bottom(),
        (rect.top() for rect in competing_rects),
        (rect.bottom() for rect in competing_rects),
    )
    half_size = QPointF(
        drag_intent_size.width() / 2.0,
        drag_intent_size.height() / 2.0,
    )
    tried: set[tuple[int, int]] = set()
    for y in y_samples:
        for x in x_samples:
            pointer = QPointF(x, y) + drag_grab_offset - half_size
            native_pointer = QPoint(round(pointer.x()), round(pointer.y()))
            identity = (native_pointer.x(), native_pointer.y())
            if identity in tried or not pointer_bounds.contains(native_pointer):
                continue
            tried.add(identity)
            intent_center = QPointF(native_pointer) - drag_grab_offset + half_size
            if not placement.hit_rect.contains(intent_center):
                continue
            intent_rect = QRectF(
                intent_center.x() - half_size.x(),
                intent_center.y() - half_size.y(),
                drag_intent_size.width(),
                drag_intent_size.height(),
            )
            selected = placement_for_drag_rect(
                snapshot,
                intent_rect,
                active_placement_id=active_placement_id,
            )
            if selected is not None and selected.target == placement.target:
                return native_pointer
    raise RuntimeError(
        "Reorder drag sweep target has no reachable pointer position: "
        f"target={placement.target!r}:hit={placement.hit_rect!r}:"
        f"active_id={active_placement_id!r}"
    )


def _wait_for_condition(
    predicate: Callable[[], bool], *, timeout_ms: int = 1_000
) -> bool:
    """Run queued Qt work until a coherent sweep topology is observable."""

    remaining_ms = timeout_ms
    while not predicate() and remaining_ms > 0:
        loop = QEventLoop()
        interval_ms = min(5, remaining_ms)
        QTimer.singleShot(interval_ms, loop.quit)
        loop.exec()
        remaining_ms -= interval_ms
    return predicate()


def _axis_samples(
    start: float,
    end: float,
    competing_starts: Iterable[float],
    competing_ends: Iterable[float],
) -> tuple[float, ...]:
    """Sample the center and each interval split by competing hit boundaries."""

    boundaries = {start, end}
    boundaries.update(min(end, max(start, value)) for value in competing_starts)
    boundaries.update(min(end, max(start, value)) for value in competing_ends)
    ordered = sorted(boundaries)
    center = (start + end) / 2.0
    samples = [center]
    samples.extend(
        (lower + upper) / 2.0
        for lower, upper in zip(ordered, ordered[1:], strict=False)
        if lower < upper
    )
    return tuple(dict.fromkeys(samples))
