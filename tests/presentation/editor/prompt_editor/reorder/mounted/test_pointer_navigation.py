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

"""Verify mounted prompt reorder pointer navigation."""

from __future__ import annotations

from typing import Any, cast


from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea, QWidget

from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCommitIntent,
)

from .mount_support import (
    ensure_qapp,
    process_events,
    _create_overlay,
    _pointer_regions,
    _chip_by_segment_index,
    _preview_rect,
    _drag_chip_to_global,
)


def test_segment_reorder_overlay_keeps_preview_geometry_for_long_drag(
    widgets: list[QWidget],
) -> None:
    """Long-prompt drag target changes should keep complete preview geometry."""

    app = ensure_qapp()
    text = ", ".join(f"tag{i:03d}" for i in range(130))
    _editor, overlay = _create_overlay(
        widgets,
        width=720,
        height=260,
        text=text,
    )
    first_chip = _chip_by_segment_index(overlay, 0)
    second_chip = _chip_by_segment_index(overlay, 1)
    preview_signal_count = 0

    def record_preview_signal() -> None:
        """Record preview sync requests emitted after the test drag starts."""

        nonlocal preview_signal_count
        preview_signal_count += 1

    overlay.previewLayoutChanged.connect(record_preview_signal)
    drag_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        second_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    QTest.mouseMove(second_chip.overlay, second_chip.mapFromGlobal(drag_target), 10)
    process_events(app)

    assert preview_signal_count >= 2
    assert overlay.preview_build_facts.snapshot().drop_target is not None
    assert overlay.ordered_chip_indices()[0] == 1
    assert _preview_rect(overlay, 1) is not None


def test_segment_reorder_overlay_updates_visual_order_across_wrapped_rows(
    widgets: list[QWidget],
) -> None:
    """Dragging a chip between wrapped rows should update the overlay order."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=170,
        height=180,
        text="alpha, beta, gamma, delta",
    )

    chips = _pointer_regions(overlay)
    assert len({chip.geometry().top() for chip in chips}) > 1

    dragged_chip = _chip_by_segment_index(overlay, 3)
    target_chip = _chip_by_segment_index(overlay, 1)
    _drag_chip_to_global(
        dragged_chip,
        global_target=target_chip.mapToGlobal(
            QPoint(target_chip.rect().left() + 4, target_chip.rect().center().y())
        ),
    )
    process_events(app)

    assert overlay.ordered_chip_indices() == [0, 3, 1, 2]
    assert overlay.has_reordered() is True


def test_segment_reorder_overlay_uses_editor_scrollbar_for_long_prompts(
    widgets: list[QWidget],
) -> None:
    """Long prompts should keep the editor scrollbar as the only scroll surface."""

    editor, overlay = _create_overlay(
        widgets,
        width=260,
        height=120,
        text=", ".join(
            f"long segment {index} with extra detail" for index in range(14)
        ),
    )

    chip_rows = {chip.geometry().top() for chip in _pointer_regions(overlay)[:4]}

    assert editor.verticalScrollBar().maximum() > 0
    assert len(chip_rows) > 1
    assert overlay.findChild(QScrollArea, "segmentReorderScrollArea") is None
    assert overlay.findChild(QWidget, "segmentReorderFrame") is None


def test_segment_reorder_overlay_reports_no_reorder_when_drag_stays_in_place(
    widgets: list[QWidget],
) -> None:
    """Starting and ending a drag in the same slot should remain a no-op."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )

    dragged_chip = _chip_by_segment_index(overlay, 1)
    QTest.mouseClick(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    process_events(app)

    assert overlay.ordered_chip_indices() == [0, 1, 2]
    assert overlay.has_reordered() is False
    assert overlay.pointer_reorder_state().dragged_segment_index is None


def test_segment_reorder_overlay_emits_typed_pointer_drop_snapshot(
    widgets: list[QWidget],
) -> None:
    """Pointer drops should publish prepared reorder state as a typed intent."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )
    commit_intents: list[PromptReorderCommitIntent] = []
    overlay.set_commit_handler(commit_intents.append)

    dragged_chip = _chip_by_segment_index(overlay, 1)
    first_chip = _chip_by_segment_index(overlay, 0)
    drag_target = first_chip.mapToGlobal(
        QPoint(first_chip.rect().left() + 4, first_chip.rect().center().y())
    )
    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(drag_target), 10)
    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(drag_target),
    )
    process_events(app)

    assert len(commit_intents) == 1
    intent = commit_intents[0]
    assert intent.reason == "pointer_drop"
    assert intent.snapshot is not None
    assert intent.snapshot.has_reordered is True
    assert intent.snapshot.ordered_chip_indices == tuple(overlay.ordered_chip_indices())
    assert intent.snapshot.layout_view is overlay.current_layout_view()


def test_segment_reorder_overlay_autoscrolls_editor_scrollbar_while_dragging_near_viewport_edge(
    widgets: list[QWidget],
) -> None:
    """Dragging near the viewport edge should advance the editor scrollbar."""

    app = ensure_qapp()
    editor, overlay = _create_overlay(
        widgets,
        width=240,
        height=120,
        text=", ".join(
            f"segment {index} with a longer description" for index in range(12)
        ),
    )

    scrollbar = editor.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(0)
    process_events(app)

    dragged_chip = _chip_by_segment_index(overlay, 0)
    initial_scroll_value = scrollbar.value()
    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(
        dragged_chip.overlay,
        dragged_chip.mapFromGlobal(
            overlay.mapToGlobal(QPoint(overlay.width() // 2, overlay.height() - 2))
        ),
        10,
    )
    cast(Any, overlay)._autoscroll.apply_step_for_tests()
    scrolled = scrollbar.value() > initial_scroll_value
    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(
            overlay.mapToGlobal(QPoint(overlay.width() // 2, overlay.height() - 2))
        ),
        delay=10,
    )
    process_events(app)

    assert scrolled
