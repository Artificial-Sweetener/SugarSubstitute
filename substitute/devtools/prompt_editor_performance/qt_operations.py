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

"""Qt operation timings for prompt editor performance scenarios."""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import cast

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QContextMenuEvent, QImage, QPainter, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptSpellingDiagnosticPayload,
)
from substitute.devtools.prompt_editor_performance.metrics import Instrumentation
from substitute.devtools.prompt_editor_performance.reorder_measurements import (
    build_reorder_measurement_state,
    capture_reorder_interaction_counts,
    chip_drop_target_global,
    current_reorder_overlay,
    exercise_reorder_geometry_caches,
    overlay_chip_by_segment_index,
    surface_for,
)
from substitute.devtools.prompt_editor_performance.scenarios import (
    ReorderArrowKey,
    ReorderDragMode,
    Scenario,
    ScenarioOperation,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync import (
    PromptReorderPreviewScheduler,
)
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    PromptShellContextMenuController,
)


QT_REORDER_ARROW_KEYS: dict[ReorderArrowKey, Qt.Key] = {
    "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right,
    "up": Qt.Key.Key_Up,
    "down": Qt.Key.Key_Down,
}


def run_scenario_operations(
    *,
    app: QApplication,
    editor: PromptEditor,
    scenario: Scenario,
    instrumentation: Instrumentation,
    extra_counts: dict[str, int | float],
) -> list[float]:
    """Run the configured operations and return per-operation timings."""

    if scenario.operation in {"type", "autocomplete", "ghost_text"}:
        return [
            time_key_click(app, editor, character=character)
            for character in scenario.typed_text
        ]

    if scenario.operation in {"backspace", "delete", "enter"}:
        key = operation_key(scenario.operation)
        return [
            time_key_click(app, editor, key=key)
            for _ in range(scenario.operation_count or 1)
        ]

    if scenario.operation == "cursor_move":
        return time_cursor_move_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "selection_change":
        return time_selection_change_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation in {"paste", "paste_import"}:
        return [
            time_paste_operation(
                app,
                editor,
                clipboard_text=scenario.clipboard_text,
            )
        ]
    if scenario.operation == "projection_paint_cache":
        return time_projection_paint_cache_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation == "diagnostic_cache":
        return time_diagnostic_cache_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation == "fill_band_cache":
        return time_fill_band_cache_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation == "scroll":
        return time_scroll_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "resize":
        return time_resize_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "hover":
        return time_hover_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "focus":
        return time_focus_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "context_menu":
        return [time_context_menu_open(app, editor)]
    if scenario.operation == "reorder_drag":
        return time_reorder_drag_operations(
            app,
            editor,
            scenario.operation_count or 1,
            instrumentation,
        )
    if scenario.operation == "reorder_alt_drag":
        return time_reorder_alt_drag_operations(
            app,
            editor,
            scenario.operation_count or 1,
            mode=scenario.reorder_drag_mode,
            extra_counts=extra_counts,
        )
    if scenario.operation == "reorder_alt_arrow":
        return time_reorder_alt_arrow_operations(
            app,
            editor,
            scenario.reorder_keys,
            extra_counts=extra_counts,
        )
    raise ValueError(f"Unsupported performance operation: {scenario.operation}")


def operation_key(operation: ScenarioOperation) -> Qt.Key:
    """Return the Qt key used for one non-text edit operation."""

    if operation == "backspace":
        return Qt.Key.Key_Backspace
    if operation == "delete":
        return Qt.Key.Key_Delete
    if operation == "enter":
        return Qt.Key.Key_Return
    raise ValueError(f"Unsupported key operation: {operation}")


def time_key_click(
    app: QApplication,
    editor: PromptEditor,
    *,
    character: str | None = None,
    key: Qt.Key | None = None,
) -> float:
    """Return elapsed milliseconds for one key operation plus event processing."""

    started_at = perf_counter()
    if character is not None:
        QTest.keyClicks(editor, character)
    elif key is not None:
        QTest.keyClick(editor, key)
    else:
        raise ValueError("A character or key is required for performance timing.")
    process_events(app)
    return (perf_counter() - started_at) * 1000.0


def time_cursor_move_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure user-facing left/right cursor movement."""

    timings: list[float] = []
    for index in range(count):
        key = Qt.Key.Key_Left if index % 2 == 0 else Qt.Key.Key_Right
        timings.append(time_key_click(app, editor, key=key))
    return timings


def time_selection_change_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure user-facing selection extension and contraction."""

    timings: list[float] = []
    for index in range(count):
        key = Qt.Key.Key_Right if index % 2 == 0 else Qt.Key.Key_Left
        started_at = perf_counter()
        QTest.keyClick(editor, key, Qt.KeyboardModifier.ShiftModifier)
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_paste_operation(
    app: QApplication,
    editor: PromptEditor,
    *,
    clipboard_text: str,
) -> float:
    """Measure one public paste operation with deterministic clipboard text."""

    QApplication.clipboard().setText(clipboard_text)
    started_at = perf_counter()
    editor.paste()
    process_events(app)
    return (perf_counter() - started_at) * 1000.0


def time_projection_paint_cache_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure projection content cache reuse through normal viewport rendering."""

    surface = surface_for(editor)
    timings: list[float] = []
    for _ in range(count):
        image = QImage(
            surface.viewport().size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(0)
        painter = QPainter(image)
        started_at = perf_counter()
        try:
            surface.viewport().render(painter, QPoint(0, 0))
        finally:
            painter.end()
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_diagnostic_cache_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure diagnostic fragment cache lookup and incremental preservation."""

    surface = surface_for(editor)
    diagnostic = spelling_diagnostic_for_text(editor.toPlainText())
    surface.set_diagnostics((diagnostic,))
    process_events(app)
    fragment_reader = cast(
        Callable[..., tuple[QRectF, ...]],
        getattr(surface, "_diagnostic_fragments_for_paint"),
    )
    timings: list[float] = []
    for _ in range(count):
        started_at = perf_counter()
        fragment_reader(
            diagnostic,
            viewport_rect=QRectF(surface.viewport().rect()),
            scroll_offset=float(surface.verticalScrollBar().value()),
        )
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)

    preserver = cast(
        Callable[..., None],
        getattr(surface, "_preserve_diagnostic_fragment_cache_for_incremental_edit"),
    )
    diagnostic_painter = getattr(surface, "_diagnostic_painter")
    next_layout_revision = int(getattr(diagnostic_painter, "_layout_revision")) + 1
    started_at = perf_counter()
    preserver(
        start=len(editor.toPlainText()),
        end=len(editor.toPlainText()),
        replacement_text="",
        next_layout_revision=next_layout_revision,
    )
    process_events(app)
    timings.append((perf_counter() - started_at) * 1000.0)

    set_cursor_position(editor, len(editor.toPlainText()))
    timings.append(time_key_click(app, editor, character="x"))
    return timings


def spelling_diagnostic_for_text(text: str) -> PromptDiagnostic:
    """Return one deterministic spelling diagnostic for cache measurement."""

    word = "mispelled"
    source_start = text.find(word)
    if source_start < 0:
        source_start = 0
    source_end = source_start + len(word)
    return PromptDiagnostic(
        diagnostic_id=f"spelling:{source_start}:{source_end}:{word}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.WARNING,
        source_start=source_start,
        source_end=source_end,
        message="Spelling issue",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


def time_fill_band_cache_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure source-line chrome fill-band cache lookup and reuse."""

    editor.set_source_line_chrome_enabled(True)
    editor.set_source_line_content_left_inset(32.0)
    process_events(app)
    surface = surface_for(editor)
    timings: list[float] = []
    for _ in range(count):
        started_at = perf_counter()
        surface.visible_prompt_fill_band_rects()
        surface.source_line_rects()
        surface.current_source_line_index()
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_scroll_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure scrollbar updates on the projection surface."""

    surface = surface_for(editor)
    scroll_bar = surface.verticalScrollBar()
    scroll_bar.setRange(0, max(scroll_bar.maximum(), count * 24))
    timings: list[float] = []
    for index in range(count):
        started_at = perf_counter()
        scroll_bar.setValue(min(scroll_bar.maximum(), (index + 1) * 24))
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_resize_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure prompt editor resize operations with event processing."""

    timings: list[float] = []
    for index in range(count):
        width = 680 + (index % 4) * 32
        height = 170 + (index % 3) * 12
        started_at = perf_counter()
        editor.resize(width, height)
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_hover_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure passive viewport hover movement over prepared projection tokens."""

    surface = surface_for(editor)
    viewport = surface.viewport()
    timings: list[float] = []
    for index in range(count):
        point = QPoint(12 + (index % 4) * 18, 12 + (index % 3) * 18)
        started_at = perf_counter()
        QTest.mouseMove(viewport, point)
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


def time_focus_operations(
    app: QApplication,
    editor: PromptEditor,
    count: int,
) -> list[float]:
    """Measure focus transitions through shell-owned focus routing."""

    timings: list[float] = []
    for _ in range(count):
        started_at = perf_counter()
        editor.clearFocus()
        process_events(app)
        editor.setFocus()
        process_events(app)
        timings.append((perf_counter() - started_at) * 1000.0)
    return timings


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
    started_at = perf_counter()
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    extra_counts["alt_open_ms"] = (perf_counter() - started_at) * 1000.0

    overlay = current_reorder_overlay(editor)
    timings: list[float] = []
    try:
        for key in keys:
            started_at = perf_counter()
            QTest.keyPress(
                editor,
                QT_REORDER_ARROW_KEYS[key],
                Qt.KeyboardModifier.AltModifier,
            )
            process_events(app)
            timings.append((perf_counter() - started_at) * 1000.0)
        capture_reorder_interaction_counts(overlay, extra_counts)
    finally:
        started_at = perf_counter()
        QTest.keyRelease(editor, Qt.Key.Key_Alt)
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
    started_at = perf_counter()
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    extra_counts["alt_open_ms"] = (perf_counter() - started_at) * 1000.0

    overlay = current_reorder_overlay(editor)
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
        for target in targets:
            started_at = perf_counter()
            QTest.mouseMove(
                dragged_chip.overlay,
                dragged_chip.overlay.mapFromGlobal(target),
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
        QTest.keyRelease(editor, Qt.Key.Key_Alt)
        process_events(app)
        extra_counts["alt_release_ms"] = (perf_counter() - started_at) * 1000.0
    return timings


def time_context_menu_open(app: QApplication, editor: PromptEditor) -> float:
    """Measure prompt context-menu opening with menu execution patched to no-op."""

    context_menu = cast(
        PromptShellContextMenuController,
        getattr(editor, "_shell_context_menu"),
    )
    position = editor.cursorRect().center()
    global_position = editor.mapToGlobal(position)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        position,
        global_position,
    )
    started_at = perf_counter()
    context_menu.show_prompt_context_menu(event)
    process_events(app)
    return (perf_counter() - started_at) * 1000.0


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

    scheduler = PromptReorderPreviewScheduler(
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


def set_cursor_position(editor: PromptEditor, position: int) -> None:
    """Move the editor caret to one source offset before measuring operations."""

    cursor = editor.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    editor.setTextCursor(cursor)


def process_events(app: QApplication, cycles: int = 3) -> None:
    """Flush a bounded number of Qt event-loop turns."""

    for _ in range(cycles):
        app.processEvents()


__all__ = [
    "QT_REORDER_ARROW_KEYS",
    "operation_key",
    "process_events",
    "run_scenario_operations",
    "set_cursor_position",
    "spelling_diagnostic_for_text",
    "time_context_menu_open",
    "time_cursor_move_operations",
    "time_diagnostic_cache_operations",
    "time_fill_band_cache_operations",
    "time_focus_operations",
    "time_hover_operations",
    "time_key_click",
    "time_paste_operation",
    "time_projection_paint_cache_operations",
    "time_reorder_alt_arrow_operations",
    "time_reorder_alt_drag_operations",
    "time_reorder_drag_operations",
    "time_resize_operations",
    "time_scroll_operations",
    "time_selection_change_operations",
]
