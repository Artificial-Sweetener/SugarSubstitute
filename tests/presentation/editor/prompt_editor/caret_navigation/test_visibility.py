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

"""Verify focus, selection, editing, and timer-driven caret visibility."""

from __future__ import annotations


import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.caret_navigation.support import (
    _restart_surface_caret_blink_cycle,
    _surface_should_paint_caret,
)

_STABLE_CURSOR_FLASH_TIME_MS = 60_000


def test_projection_surface_focused_caret_starts_visible(
    widgets: list[QWidget],
) -> None:
    """Focusing the prompt editor should show the custom caret immediately."""

    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    _restart_surface_caret_blink_cycle(box)

    assert _surface_should_paint_caret(box) is True


def test_projection_surface_owns_actual_focus_for_prompt_editor_facade(
    widgets: list[QWidget],
) -> None:
    """Prompt editor focus should resolve to the projection surface, not QTextEdit."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    surface = surface_for(box)
    process_events(app)

    assert box.hasFocus() is True
    assert surface.hasFocus() is True
    assert app.focusWidget() is surface


def test_projection_surface_caret_blinks_after_half_cycle(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The custom caret should toggle visibility using the surface flash-time seam."""

    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: _STABLE_CURSOR_FLASH_TIME_MS,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    _restart_surface_caret_blink_cycle(box)
    surface = surface_for(box)

    assert _surface_should_paint_caret(box) is True

    surface._caret_visual_controller.blink_timer.timeout.emit()  # noqa: SLF001
    assert _surface_should_paint_caret(box) is False

    surface._caret_visual_controller.blink_timer.timeout.emit()  # noqa: SLF001
    assert _surface_should_paint_caret(box) is True


def test_projection_surface_caret_move_resets_blink_to_visible(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moving the caret should make the custom caret visible immediately again."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: _STABLE_CURSOR_FLASH_TIME_MS,
    )
    box = show_prompt_editor(
        widgets,
        text="ab",
        width=220,
    )
    surface_for(box).set_cursor_positions(
        cursor_position=0,
        anchor_position=0,
    )
    process_events(app)

    surface_for(box)._set_caret_blink_visible(False)  # noqa: SLF001
    assert _surface_should_paint_caret(box) is False

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert _surface_should_paint_caret(box) is True


def test_projection_surface_selection_hides_caret(
    widgets: list[QWidget],
) -> None:
    """A non-empty selection should suppress custom caret painting."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=220,
    )
    surface = surface_for(box)

    surface.set_cursor_positions(
        cursor_position=5,
        anchor_position=0,
    )
    process_events(app)

    assert _surface_should_paint_caret(box) is False


def test_projection_surface_collapsing_selection_restores_caret(
    widgets: list[QWidget],
) -> None:
    """Collapsing an existing selection should restore custom caret painting."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha beta",
        width=220,
    )
    surface = surface_for(box)

    surface.set_cursor_positions(
        cursor_position=5,
        anchor_position=0,
    )
    process_events(app)
    assert _surface_should_paint_caret(box) is False

    surface.set_cursor_positions(
        cursor_position=5,
        anchor_position=5,
    )
    process_events(app)

    assert _surface_should_paint_caret(box) is True


def test_projection_surface_text_edit_resets_blink_to_visible(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typing should make the custom caret visible immediately again."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: _STABLE_CURSOR_FLASH_TIME_MS,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )

    surface_for(box)._set_caret_blink_visible(False)  # noqa: SLF001
    assert _surface_should_paint_caret(box) is False

    QTest.keyClicks(box, "a")
    process_events(app)

    assert _surface_should_paint_caret(box) is True


def test_projection_surface_focus_loss_hides_caret(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Losing focus should stop painting the custom caret immediately."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: _STABLE_CURSOR_FLASH_TIME_MS,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    other = QWidget()
    other.resize(120, 80)
    other.show()
    other.activateWindow()
    other.raise_()
    other.setFocus()
    widgets.append(other)
    process_events(app)

    assert _surface_should_paint_caret(box) is False


def test_projection_surface_non_blinking_setting_keeps_caret_visible(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disabled system blink setting should keep the custom caret continuously visible."""

    app = ensure_qapp()
    monkeypatch.setattr(
        PromptProjectionSurface,
        "_cursor_flash_time_ms",
        lambda self: 0,
    )
    box = show_prompt_editor(
        widgets,
        text="",
        width=220,
    )
    surface = surface_for(box)

    process_events(app)

    assert _surface_should_paint_caret(box) is True
    assert surface._caret_visual_controller.blink_timer.isActive() is False  # noqa: SLF001
