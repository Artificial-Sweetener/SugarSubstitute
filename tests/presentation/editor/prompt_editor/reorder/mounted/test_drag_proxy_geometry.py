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

"""Verify mounted prompt reorder drag proxy geometry."""

from __future__ import annotations


from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.overlays import (
    PromptReorderDragIntent,
)

from .mount_support import (
    ensure_qapp,
    process_events,
    _create_overlay,
    _chip_by_segment_index,
    _drag_proxy,
)


def test_segment_reorder_overlay_keeps_drag_proxy_above_pointer(
    widgets: list[QWidget],
) -> None:
    """The held chip proxy should stay near the pointer while sizing itself safely."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="Held, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 0)
    proxy = _drag_proxy(overlay)
    target_global = dragged_chip.mapToGlobal(
        dragged_chip.rect().center() + QPoint(80, 18)
    )

    assert proxy.testAttribute(Qt.WidgetAttribute.WA_StyledBackground) is False
    assert proxy.inherits("QFrame") is True

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(target_global), 10)
    process_events(app)

    proxy_parent = proxy.parentWidget()
    assert proxy_parent is not None
    pointer_in_proxy_host = proxy_parent.mapFromGlobal(target_global)

    assert proxy.isVisible() is True
    assert proxy.parentWidget() is not overlay
    assert proxy.width() > 0
    assert proxy.height() > 0
    assert (
        proxy.geometry().left() <= pointer_in_proxy_host.x() <= proxy.geometry().right()
    )
    assert -2 <= proxy.geometry().bottom() - pointer_in_proxy_host.y() <= 6
    proxy_mask = proxy.mask()
    assert proxy_mask.contains(proxy.rect().center()) is True
    assert proxy_mask.contains(QPoint(0, 0)) is False

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    process_events(app)

    assert proxy.isVisible() is False


def test_segment_reorder_overlay_drag_proxy_can_escape_overlay_bounds(
    widgets: list[QWidget],
) -> None:
    """The floating drag proxy should only escape the prompt viewport by a small bounded margin."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="Held, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 0)
    proxy = _drag_proxy(overlay)
    target_global = overlay.mapToGlobal(
        QPoint(overlay.width() // 2, overlay.height() + 40)
    )

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(target_global), 10)
    process_events(app)

    proxy_bottom_global = proxy.mapToGlobal(proxy.rect().bottomLeft()).y()
    overlay_bottom_global = overlay.mapToGlobal(overlay.rect().bottomLeft()).y()

    assert proxy.isVisible() is True
    assert proxy_bottom_global > overlay_bottom_global
    assert proxy_bottom_global <= overlay_bottom_global + 20

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_cancel_restores_drag_state(
    widgets: list[QWidget],
) -> None:
    """Cancel should restore public drag state without mutating source text."""

    app = ensure_qapp()
    editor, overlay = _create_overlay(
        widgets,
        width=420,
        height=180,
        text="alpha, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 1)
    first_chip = _chip_by_segment_index(overlay, 0)
    proxy = _drag_proxy(overlay)
    target_global = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.rect().center(),
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(target_global), 10)
    process_events(app)

    assert overlay.pointer_reorder_state().dragged_segment_index == 1
    assert proxy.isVisible() is True

    overlay.cancel_drag()
    process_events(app)

    assert editor.toPlainText() == "alpha, beta, gamma"
    assert overlay.pointer_reorder_state().dragged_segment_index is None
    assert overlay.preview_build_facts.snapshot().drop_target is None
    assert overlay.ordered_chip_indices() == [0, 1, 2]
    assert overlay.has_reordered() is False
    pointer_state = overlay.pointer_reorder_state()
    preview_state = overlay.preview_target_state()
    assert pointer_state.dragged_segment_index is None
    assert pointer_state.active_drop_target is None
    assert preview_state.active_target is None
    assert preview_state.has_preview_layout is False
    assert proxy.isVisible() is False

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(target_global),
        delay=10,
    )
    process_events(app)


def test_segment_reorder_overlay_position_refresh_key_tracks_viewport_changes(
    widgets: list[QWidget],
) -> None:
    """The cheap position key should skip unchanged viewports and catch resizes."""

    app = ensure_qapp()
    editor, overlay = _create_overlay(
        widgets,
        width=360,
        height=180,
        text="alpha, beta, gamma",
    )

    assert overlay.needs_position_refresh(reason="unchanged") is False

    host = editor.parentWidget()
    assert host is not None
    host.resize(420, 220)
    process_events(app)

    assert overlay.needs_position_refresh(reason="resized") is True


def test_segment_reorder_overlay_preserves_grab_offset_in_drag_intent_rect(
    widgets: list[QWidget],
) -> None:
    """Held-chip target geometry should preserve the original pointer grab offset."""

    app = ensure_qapp()
    _editor, overlay = _create_overlay(
        widgets,
        width=560,
        height=180,
        text="wide descriptive chip, beta, gamma",
    )
    dragged_chip = _chip_by_segment_index(overlay, 0)
    drag_intents: list[PromptReorderDragIntent] = []
    overlay.set_drag_handler(drag_intents.append)
    press_pos = QPoint(
        max(1, dragged_chip.rect().right() - 5),
        dragged_chip.rect().center().y(),
    )
    move_global = dragged_chip.mapToGlobal(press_pos + QPoint(48, 0))

    QTest.mousePress(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=press_pos,
    )
    QTest.mouseMove(dragged_chip.overlay, dragged_chip.mapFromGlobal(move_global), 10)
    process_events(app)

    pointer_state = overlay.pointer_reorder_state()
    intent_rect = pointer_state.last_drag_intent_rect
    assert intent_rect is not None
    grab_offset = pointer_state.drag_grab_offset
    assert grab_offset is not None
    drag_intent_size = pointer_state.drag_intent_size
    assert drag_intent_size is not None
    assert 0.0 < grab_offset.x() < drag_intent_size.width()
    assert 0.0 <= grab_offset.y() < drag_intent_size.height()
    assert drag_intents
    expected_top_left = (
        QPointF(overlay.mapFromGlobal(drag_intents[-1].global_position)) - grab_offset
    )

    assert abs(intent_rect.topLeft().x() - expected_top_left.x()) < 0.01
    assert abs(intent_rect.topLeft().y() - expected_top_left.y()) < 0.01
    assert intent_rect.size() == drag_intent_size

    QTest.mouseRelease(
        dragged_chip.overlay,
        Qt.MouseButton.LeftButton,
        pos=dragged_chip.mapFromGlobal(move_global),
        delay=10,
    )
    process_events(app)
