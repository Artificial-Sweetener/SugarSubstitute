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

"""Verify SugarSubstitute's semantic Input canvas cursor artwork."""

from __future__ import annotations

from cutecanvas import EditorCursorIntent
from PySide6.QtCore import (
    QCoreApplication,
    QPoint,
    QSize,
    QSizeF,
    qInstallMessageHandler,
)
from PySide6.QtWidgets import QApplication

from substitute.presentation.canvas.input.input_canvas_cursor_theme import (
    InputCanvasCursorTheme,
)


def _app() -> QApplication:
    """Return the shared Qt application required by cursor construction."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def test_input_cursor_theme_defers_non_branded_feedback() -> None:
    """CuteCanvas should retain ownership of cursor families Sugar does not theme."""

    _app()
    theme = InputCanvasCursorTheme()

    assert (
        theme.resolve_cursor(
            EditorCursorIntent.PRECISE,
            device_pixel_ratio=1.0,
        )
        is None
    )


def test_selection_translation_cursor_is_cached_and_dpr_aware() -> None:
    """Fluent-derived boundary movement should retain logical size and hotspot."""

    _app()
    theme = InputCanvasCursorTheme()

    one_x = theme.resolve_cursor(
        EditorCursorIntent.SELECTION_TRANSLATE,
        device_pixel_ratio=1.0,
    )
    one_x_repeated = theme.resolve_cursor(
        EditorCursorIntent.SELECTION_TRANSLATE,
        device_pixel_ratio=1.0,
    )
    two_x = theme.resolve_cursor(
        EditorCursorIntent.SELECTION_TRANSLATE,
        device_pixel_ratio=2.0,
    )

    assert one_x is not None and one_x_repeated is not None and two_x is not None
    assert one_x.hotSpot() == two_x.hotSpot() == QPoint(6, 3)
    assert one_x.pixmap().deviceIndependentSize() == QSizeF(40.0, 40.0)
    assert two_x.pixmap().deviceIndependentSize() == QSizeF(40.0, 40.0)
    assert two_x.pixmap().size() == QSize(80, 80)
    assert one_x.pixmap().cacheKey() == one_x_repeated.pixmap().cacheKey()


def test_move_cursor_switches_from_arrows_to_scissors_without_losing_hotspot() -> None:
    """Move semantics must distinguish normal movement from selected-pixel lift."""
    _app()
    theme = InputCanvasCursorTheme()

    normal = theme.resolve_cursor(EditorCursorIntent.MOVE, device_pixel_ratio=1.5)
    cut = theme.resolve_cursor(EditorCursorIntent.MOVE_CUT, device_pixel_ratio=1.5)

    assert normal is not None and cut is not None
    assert normal.hotSpot() == cut.hotSpot() == QPoint(6, 3)
    assert normal.pixmap().size() == cut.pixmap().size() == QSize(60, 60)
    assert normal.pixmap().cacheKey() != cut.pixmap().cacheKey()


def test_move_cut_cursor_normalizes_transient_invalid_display_scale() -> None:
    """A transient zero DPR must never create an unpaintable cursor image."""

    _app()
    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda _kind, _context, message: messages.append(message)
    )
    try:
        cursor = InputCanvasCursorTheme().resolve_cursor(
            EditorCursorIntent.MOVE_CUT,
            device_pixel_ratio=0.0,
        )
    finally:
        qInstallMessageHandler(previous_handler)

    assert cursor is not None and not cursor.pixmap().isNull()
    assert not any("QPainter" in message for message in messages)
