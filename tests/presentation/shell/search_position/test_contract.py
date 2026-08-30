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

"""Contract tests for floating search overlay behavior."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QEvent, QPoint, Qt

from substitute.presentation.shell.search_overlay_controller import (
    SearchOverlayController,
)


class _SearchBox:
    """Minimal floating search-box double for geometry assertions."""

    def __init__(self) -> None:
        """Initialize the box with deterministic width."""

        self._width = 120
        self.moves: list[tuple[int, int]] = []
        self.raised = 0
        self.hidden = 0
        self.shown = 0
        self.adjusted = 0
        self._visible = False
        self.search_bar = _SearchBar()

    def width(self) -> int:
        """Return the current widget width."""

        return self._width

    def adjustSize(self) -> None:
        """Accept size-adjust requests."""

        self.adjusted += 1

    def move(self, x: int, y: int) -> None:
        """Record the requested target point."""

        self.moves.append((x, y))

    def raise_(self) -> None:
        """Record raise requests."""

        self.raised += 1

    def searchLineEdit(self) -> "_SearchBar":
        """Return the embedded search line edit."""

        return self.search_bar

    def hide(self) -> None:
        """Record hide requests."""

        self.hidden += 1
        self._visible = False

    def show(self) -> None:
        """Record show requests."""

        self.shown += 1
        self._visible = True

    def isVisible(self) -> bool:
        """Return the fake visibility state."""

        return self._visible


class _SearchBar:
    """Search line edit double for keyboard shortcut assertions."""

    def __init__(self) -> None:
        """Initialize recorded focus calls."""

        self.focused = 0
        self.selected = 0

    def setFocus(self) -> None:
        """Record focus requests."""

        self.focused += 1

    def selectAll(self) -> None:
        """Record select-all requests."""

        self.selected += 1


class _Panel:
    """Editor-panel double exposing mapTo/local sizing used by centering logic."""

    def __init__(self) -> None:
        """Initialize the deterministic panel geometry."""

        self._origin = QPoint(240, 48)
        self._width = 640

    def mapTo(self, _parent: object, point: QPoint) -> QPoint:
        """Return the mapped local-origin point inside the shell."""

        assert point == QPoint(0, 0)
        return QPoint(self._origin.x(), self._origin.y())

    def width(self) -> int:
        """Return the visible editor width."""

        return self._width


def test_position_search_box_centers_over_active_editor_panel() -> None:
    """Search-box placement should anchor to the active editor panel local origin."""

    search_box = _SearchBox()
    active_panel = _Panel()
    window = SimpleNamespace(
        contextSearchBox=search_box,
        active_editor_panel=active_panel,
    )

    SearchOverlayController(window).position_search_box()

    assert search_box.moves == [(500, 64)]
    assert search_box.raised == 1


def test_ctrl_f_shows_positions_and_focuses_search_bar() -> None:
    """Ctrl+F should reveal and focus the floating editor search overlay."""

    search_box = _SearchBox()
    active_panel = _Panel()
    window = SimpleNamespace(
        contextSearchBox=search_box,
        active_editor_panel=active_panel,
    )
    event = _KeyEvent(Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)

    result = SearchOverlayController(window).handle_event_filter_event(event)

    assert result is True
    assert search_box.shown == 1
    assert search_box.adjusted == 1
    assert search_box.moves == [(500, 64)]
    assert search_box.search_bar.focused == 1
    assert search_box.search_bar.selected == 1


def test_escape_closes_search_bar_and_focuses_current_match() -> None:
    """Escape should close search and return focus to the active editor match."""

    search_box = _SearchBox()
    active_panel = SimpleNamespace(focus_calls=[])
    active_panel.focus_current_search_match = lambda: active_panel.focus_calls.append(
        "match"
    )
    window = SimpleNamespace(
        contextSearchBox=search_box,
        active_editor_panel=active_panel,
        focusWidget=lambda: search_box.search_bar,
    )
    event = _KeyEvent(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)

    result = SearchOverlayController(window).handle_event_filter_event(event)

    assert result is True
    assert search_box.hidden == 1
    assert active_panel.focus_calls == ["match"]


class _KeyEvent:
    """Minimal key event double for search overlay shortcut handling."""

    def __init__(
        self,
        key: Qt.Key,
        modifiers: Qt.KeyboardModifier,
    ) -> None:
        """Store key and modifier values."""

        self._key = key
        self._modifiers = modifiers

    def type(self) -> QEvent.Type:
        """Return a key-press event type."""

        return QEvent.Type.KeyPress

    def key(self) -> Qt.Key:
        """Return the pressed key."""

        return self._key

    def modifiers(self) -> Qt.KeyboardModifier:
        """Return active keyboard modifiers."""

        return self._modifiers
