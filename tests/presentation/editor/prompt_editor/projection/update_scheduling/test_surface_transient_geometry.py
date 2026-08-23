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

"""Verify transient geometry while mounted projection work is pending."""

from __future__ import annotations


import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    delay_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.projection.update_scheduling.support import (
    _flush_projection_update_scheduler,
)


def test_projection_surface_cursor_rect_uses_transient_geometry_during_pending_typing(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caret geometry reads during safe typing should not force projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    assert not box.cursorRect().isNull()

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0


def test_projection_surface_ensure_caret_visible_uses_transient_geometry(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caret visibility maintenance during safe typing should not force projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)
    surface._ensure_caret_visible()  # noqa: SLF001

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0


def test_projection_surface_scheduled_projection_clears_transient_caret_geometry(
    widgets: list[QWidget],
) -> None:
    """Authoritative projection commits should retire temporary caret geometry."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert (
        surface._transient_edit_overlays.caret_geometry is not None  # noqa: SLF001
    )

    _flush_projection_update_scheduler(surface)
    process_events(app)

    assert surface.has_pending_projection_update() is False
    assert surface._transient_edit_overlays.caret_geometry is None  # noqa: SLF001


def test_projection_surface_hit_testing_flushes_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact hit-testing should force pending projection work to apply."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001
    rebuild_count = 0

    def count_rebuild() -> None:
        """Record projection rebuilds while preserving production behavior."""

        nonlocal rebuild_count
        rebuild_count += 1
        original_rebuild_projection()

    monkeypatch.setattr(surface, "_rebuild_projection", count_rebuild)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )
    rebuild_count = 0

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    assert rebuild_count == 0

    box.cursorForPosition(QPoint(4, 4))

    assert surface.has_pending_projection_update() is False
    assert rebuild_count == 0


def test_projection_surface_hover_move_does_not_flush_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hover tracking must not force safe-typing projection work onto mouse move."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    flush_count = 0

    def count_flush(*, reason: str) -> None:
        """Record unexpected mouse-move flushes without applying them."""

        nonlocal flush_count
        del reason
        flush_count += 1

    monkeypatch.setattr(surface, "_flush_pending_projection_update", count_flush)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(4.0, 4.0),
        QPointF(4.0, 4.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(surface.viewport(), event)

    assert flush_count == 0
    assert surface.has_pending_projection_update() is True


def test_projection_surface_resize_does_not_flush_pending_projection_update(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resize should reflow prepared geometry without forcing stale-safe projection."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), ",
        width=240,
    )
    surface = surface_for(box)
    delay_projection_update_scheduler(surface)
    cursor_position = len(box.toPlainText())
    surface.set_cursor_positions(
        cursor_position=cursor_position,
        anchor_position=cursor_position,
    )

    QTest.keyClicks(box, "x")
    flush_semantic_refresh(box)

    assert surface.has_pending_projection_update() is True
    flush_calls: list[str] = []
    rebuild_count = 0

    def record_flush(*, reason: str) -> None:
        """Record an unexpected resize projection flush."""

        flush_calls.append(reason)

    def record_rebuild() -> None:
        """Record an unexpected resize projection rebuild."""

        nonlocal rebuild_count
        rebuild_count += 1

    monkeypatch.setattr(surface, "_flush_pending_projection_update", record_flush)
    monkeypatch.setattr(surface, "_rebuild_projection", record_rebuild)

    surface.resize(surface.width() + 24, surface.height() + 8)
    process_events(ensure_qapp())

    assert flush_calls == []
    assert rebuild_count == 0
    assert surface.has_pending_projection_update() is True
