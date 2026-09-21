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

"""Measure prompt-editor reorder keyboard, pointer, and cache operations."""

from __future__ import annotations

from time import perf_counter

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_timer import (
    PromptReorderPreviewTimer,
)
from substitute.presentation.editor.prompt_editor.overlays import SegmentReorderOverlay

from .editing_operations import prompt_key_target
from .event_loop import process_events
from .metrics import Instrumentation
from .reorder_measurements import (
    build_reorder_measurement_state,
    capture_reorder_interaction_counts,
    chip_drop_target_global,
    current_reorder_overlay,
    exercise_reorder_geometry_caches,
    overlay_chip_by_segment_index,
)
from .scenarios import ReorderArrowKey, ReorderDragMode


QT_REORDER_ARROW_KEYS: dict[ReorderArrowKey, Qt.Key] = {
    "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right,
    "up": Qt.Key.Key_Up,
    "down": Qt.Key.Key_Down,
}


def time_reorder_alt_arrow_operations(
    app: QApplication,
    editor: PromptEditor,
    keys: tuple[ReorderArrowKey, ...],
    *,
    extra_counts: dict[str, int | float],
) -> list[float]:
    """Measure real PromptEditor Alt+Arrow reorder key handling."""

    if not keys:
        raise ValueError("Alt+Arrow measurement requires at least one key.")

    editor.setFocus()
    process_events(app)
    key_target = prompt_key_target(editor)
    started_at = perf_counter()
    send_prompt_alt_event(key_target, QEvent.Type.KeyPress)
    process_events(app)
    extra_counts["alt_open_ms"] = (perf_counter() - started_at) * 1000.0

    overlay = wait_for_current_reorder_overlay(app, editor)
    timings: list[float] = []
    try:
        for key in keys:
            started_at = perf_counter()
            QTest.keyPress(
                key_target,
                QT_REORDER_ARROW_KEYS[key],
                Qt.KeyboardModifier.AltModifier,
            )
            process_events(app)
            timings.append((perf_counter() - started_at) * 1000.0)
        capture_reorder_interaction_counts(overlay, extra_counts)
    finally:
        started_at = perf_counter()
        send_prompt_alt_event(key_target, QEvent.Type.KeyRelease)
        process_events(app)
        extra_counts["alt_release_ms"] = (perf_counter() - started_at) * 1000.0
    return timings


def time_reorder_alt_drag_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
    *,
    mode: ReorderDragMode,
    extra_counts: dict[str, int | float],
) -> list[float]:
    """Measure real PromptEditor Alt+Drag pointer movement handling."""

    editor.setFocus()
    process_events(app)
    key_target = prompt_key_target(editor)
    started_at = perf_counter()
    send_prompt_alt_event(key_target, QEvent.Type.KeyPress)
    process_events(app)
    extra_counts["alt_open_ms"] = (perf_counter() - started_at) * 1000.0

    overlay = wait_for_current_reorder_overlay(app, editor)
    dragged_chip = overlay_chip_by_segment_index(overlay, 1)
    first_target = chip_drop_target_global(overlay_chip_by_segment_index(overlay, 0))
    last_segment_index = max(overlay.pointer_region_rects())
    last_target = chip_drop_target_global(
        overlay_chip_by_segment_index(overlay, last_segment_index),
        trailing=True,
    )

    timings: list[float] = []
    try:
        QTest.mousePress(
            dragged_chip.overlay,
            Qt.MouseButton.LeftButton,
            pos=dragged_chip.rect().center(),
        )
        process_events(app)

        if mode == "same_target":
            QTest.mouseMove(
                dragged_chip.overlay,
                dragged_chip.overlay.mapFromGlobal(first_target),
                10,
            )
            process_events(app)
            targets = tuple(
                first_target + QPoint(1 + (index % 2), 0) for index in range(count)
            )
        else:
            targets = tuple(
                last_target if index % 2 == 0 else first_target
                for index in range(count)
            )

        editor.reset_reorder_geometry_cache_counters()
        for global_target in targets:
            started_at = perf_counter()
            QTest.mouseMove(
                dragged_chip.overlay,
                dragged_chip.overlay.mapFromGlobal(global_target),
                10,
            )
            process_events(app)
            timings.append((perf_counter() - started_at) * 1000.0)

        if mode == "target_change":
            QTest.qWait(140)
            process_events(app)
        capture_reorder_interaction_counts(overlay, extra_counts)

        QTest.mouseRelease(
            dragged_chip.overlay,
            Qt.MouseButton.LeftButton,
            pos=dragged_chip.overlay.mapFromGlobal(
                targets[-1] if targets else first_target
            ),
            delay=10,
        )
        process_events(app)
    finally:
        started_at = perf_counter()
        send_prompt_alt_event(key_target, QEvent.Type.KeyRelease)
        process_events(app)
        extra_counts["alt_release_ms"] = (perf_counter() - started_at) * 1000.0
    return timings


def time_reorder_drag_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
    instrumentation: Instrumentation,
) -> list[float]:
    """Measure latest-wins preview scheduling plus projection-owned geometry caches."""

    def run_pending() -> None:
        """Record one deterministic preview publication callback."""

        return None

    measurement_state = build_reorder_measurement_state(editor.toPlainText())
    editor.set_reorder_preview_state(measurement_state.preview_state)
    process_events(app)
    editor.reset_reorder_geometry_cache_counters()

    scheduler = PromptReorderPreviewTimer(
        interval_ms=0,
        run_pending=run_pending,
        pointer_revision=lambda: count,
    )
    timings: list[float] = []
    for index in range(count):
        first_revision = (index * 2) + 1
        latest_revision = first_revision + 1
        started_at = perf_counter()
        scheduler.request(
            revision=first_revision,
            reason="measure_reorder_drag",
            pointer_active=True,
            gesture_id=1,
            event_id=first_revision,
        )
        scheduler.request(
            revision=latest_revision,
            reason="measure_reorder_drag",
            pointer_active=True,
            gesture_id=1,
            event_id=latest_revision,
        )
        process_events(app)
        exercise_reorder_geometry_caches(editor, measurement_state)
        timings.append((perf_counter() - started_at) * 1000.0)
    scheduler.stop()
    _ = instrumentation
    return timings


def send_prompt_alt_event(target: QWidget, event_type: QEvent.Type) -> None:
    """Deliver one modifier event through the production focus-widget route."""

    if event_type not in {QEvent.Type.KeyPress, QEvent.Type.KeyRelease}:
        raise ValueError("Prompt Alt event must be a key press or release.")
    modifiers = (
        Qt.KeyboardModifier.AltModifier
        if event_type is QEvent.Type.KeyPress
        else Qt.KeyboardModifier.NoModifier
    )
    QCoreApplication.sendEvent(
        target,
        QKeyEvent(
            event_type,
            Qt.Key.Key_Alt,
            modifiers,
        ),
    )


def wait_for_current_reorder_overlay(
    app: QApplication,
    editor: PromptEditor,
    *,
    event_cycles: int = 12,
) -> SegmentReorderOverlay:
    """Return the Alt-created overlay after bounded observable event turns."""

    if event_cycles < 1:
        raise ValueError("Reorder overlay event cycles must be positive.")
    for _ in range(event_cycles):
        try:
            return current_reorder_overlay(editor)
        except RuntimeError:
            app.processEvents()
    return current_reorder_overlay(editor)


__all__ = [
    "QT_REORDER_ARROW_KEYS",
    "send_prompt_alt_event",
    "time_reorder_alt_arrow_operations",
    "time_reorder_alt_drag_operations",
    "time_reorder_drag_operations",
    "wait_for_current_reorder_overlay",
]
