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

"""Verify transient-neutral weighted-token lifecycle contracts."""

from __future__ import annotations


from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.projection_engine_support import (
    token_weight_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from ..mounting import (
    click_control_rect,
    emphasis_token_for,
    reveal_emphasis_controls,
    set_cursor_position,
    wait_for_hide_linger_timeout,
)


def test_overlay_owned_transient_neutral_emphasis_survives_caret_moves(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should ignore caret movement until overlay ownership ends."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, 2)
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(app)
    assert box.toPlainText() == "cat, dog"
    assert controls.visible_token is not None

    set_cursor_position(box, 7)
    process_events(app)

    tokens = [
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ]
    assert len(tokens) == 1
    assert tokens[0].synthetic is True


def test_overlay_owned_transient_neutral_emphasis_clears_when_controls_hide(
    widgets: list[QWidget],
) -> None:
    """Overlay-owned neutral emphasis should clear once the overlay stops owning the token."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), dog",
        width=220,
    )
    controls = token_weight_controls_for(box)

    set_cursor_position(box, len(box.toPlainText()))
    token = emphasis_token_for(box)
    reveal_emphasis_controls(box, token)
    assert controls.decrease_rect is not None

    click_control_rect(controls, controls.decrease_rect)
    process_events(app)
    assert box.toPlainText() == "cat, dog"
    assert controls.visible_token is not None

    QTest.mouseMove(
        box.viewport(),
        QPoint(max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)),
    )
    process_events(app, cycles=3)
    wait_for_hide_linger_timeout(controls)
    process_events(app, cycles=3)

    tokens = [
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ]
    assert tokens == []
