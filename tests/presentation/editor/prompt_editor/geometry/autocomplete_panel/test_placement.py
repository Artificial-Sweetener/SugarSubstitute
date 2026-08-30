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

"""Contract tests for prompt-editor autocomplete geometry helpers."""

from __future__ import annotations


from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.geometry.autocomplete_panel import (
    compute_autocomplete_panel_rect,
)


def ensure_qapp() -> QApplication:
    """Return the Qt application needed to construct geometry widgets."""

    application = QApplication.instance()
    if isinstance(application, QApplication):
        return application
    return QApplication([])


def test_compute_autocomplete_panel_rect_clamps_left_edge_inside_host() -> None:
    """Panel placement should clamp the left edge within the visible host margin."""

    ensure_qapp()
    host = QWidget()
    host.resize(320, 200)

    rect = compute_autocomplete_panel_rect(
        host,
        QRect(-24, 40, 1, 18),
        QSize(180, 72),
    )

    assert rect.left() == 4
    assert rect.right() <= host.width() - 4


def test_compute_autocomplete_panel_rect_flips_above_the_caret_when_needed() -> None:
    """Panel placement should fall back above the caret when there is no room below."""

    ensure_qapp()
    host = QWidget()
    host.resize(320, 180)
    anchor_rect = QRect(40, 152, 1, 18)

    rect = compute_autocomplete_panel_rect(
        host,
        anchor_rect,
        QSize(180, 72),
    )

    assert rect.bottom() < anchor_rect.top()
    assert rect.top() >= 4


def test_compute_autocomplete_panel_rect_shrinks_above_before_covering_caret_line() -> (
    None
):
    """Flipped placement should shrink instead of clamping back over the caret line."""

    ensure_qapp()
    host = QWidget()
    host.resize(640, 400)
    anchor_rect = QRect(40, 300, 1, 18)

    rect = compute_autocomplete_panel_rect(
        host,
        anchor_rect,
        QSize(560, 630),
    )

    assert rect.top() == 4
    assert rect.height() == 290
    assert rect.bottom() < anchor_rect.top()


def test_compute_autocomplete_panel_rect_shrinks_below_without_covering_caret_line() -> (
    None
):
    """Below placement should shrink while keeping the active text line uncovered."""

    ensure_qapp()
    host = QWidget()
    host.resize(640, 200)
    anchor_rect = QRect(40, 20, 1, 18)

    rect = compute_autocomplete_panel_rect(
        host,
        anchor_rect,
        QSize(560, 630),
    )

    assert rect.top() > anchor_rect.bottom()
    assert rect.height() == 152
    assert rect.bottom() <= host.height() - 4
