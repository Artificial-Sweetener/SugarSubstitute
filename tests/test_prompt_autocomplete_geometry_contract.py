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

import os
from collections.abc import Iterator
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRect, QSize
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.geometry import (
    autocomplete_panel_host,
    compute_autocomplete_panel_rect,
    map_cursor_rect_to_host,
)


class _SelfWindowWidget(QWidget):
    """Return itself from `window()` so host fallback behavior stays testable."""

    def window(self) -> QWidget:
        """Return this widget as its own window."""

        return self


def ensure_qapp() -> QApplication:
    """Return a running Qt application for geometry helper tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 3) -> None:
    """Flush a few event-loop turns so widget geometry becomes stable."""

    for _ in range(cycles):
        app.processEvents()


def _show_widget(widget: QWidget) -> None:
    """Show one widget and process events so mapping helpers can use global coordinates."""

    widget.show()
    process_events(ensure_qapp())


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one geometry helper test."""

    ensure_qapp()
    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_autocomplete_panel_host_prefers_editor_window(widgets: list[QWidget]) -> None:
    """Panel host selection should use the top-level window when one exists."""

    host = QWidget()
    host.resize(360, 240)
    editor = QWidget(host)
    editor.resize(220, 80)
    widgets.extend([host, editor])
    _show_widget(host)

    assert autocomplete_panel_host(editor) is host


def test_autocomplete_panel_host_falls_back_to_parent_when_window_is_unsuitable(
    widgets: list[QWidget],
) -> None:
    """Panel host selection should fall back to the parent when `window()` returns self."""

    parent = QWidget()
    parent.resize(360, 240)
    editor = _SelfWindowWidget(parent)
    editor.resize(220, 80)
    widgets.extend([parent, editor])
    _show_widget(parent)

    assert autocomplete_panel_host(editor) is parent


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


def test_map_cursor_rect_to_host_preserves_size_while_translating_coordinates(
    widgets: list[QWidget],
) -> None:
    """Cursor-rect mapping should translate position without changing rect size."""

    host = QWidget()
    host.setGeometry(40, 40, 420, 280)
    container = QWidget(host)
    container.setGeometry(36, 28, 280, 180)
    viewport = QWidget(container)
    viewport.setGeometry(12, 18, 240, 120)
    widgets.extend([host, container, viewport])
    _show_widget(host)

    cursor_rect = QRect(7, 11, 1, 18)
    mapped_rect = map_cursor_rect_to_host(viewport, cursor_rect, host)
    expected_top_left = host.mapFromGlobal(viewport.mapToGlobal(cursor_rect.topLeft()))

    assert mapped_rect.topLeft() == expected_top_left
    assert mapped_rect.size() == cursor_rect.size()
