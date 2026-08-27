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

"""Verify typed literal and emphasis source normalization."""

from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    OBJECT_REPLACEMENT_CHARACTER,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionTokenKind,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.support.prompt_editor.projection_surface_support import (
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)


def test_projection_surface_typing_implicit_parentheses_creates_stable_emphasis(
    widgets: list[QWidget],
) -> None:
    """Typing implicit parens should create explicit projected emphasis."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=240,
    )
    surface = surface_for(box)

    QTest.keyClicks(box, "painting (medium)")
    process_events(app)

    assert box.toPlainText() == "painting (medium:1.10)"
    assert surface.projection_document().projection_text == (
        f"painting {OBJECT_REPLACEMENT_CHARACTER}medium{OBJECT_REPLACEMENT_CHARACTER}"
    )
    assert len(surface.projection_document().tokens) == 1
    token = surface.projection_document().tokens[0]
    assert token.kind is PromptProjectionTokenKind.EMPHASIS
    assert token.value_text == "1.10"


def test_projection_surface_typing_standalone_weighted_emphasis_keeps_real_syntax_unescaped(
    widgets: list[QWidget],
) -> None:
    """A full standalone weighted shell should remain real emphasis syntax when typed."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=240,
    )
    surface = surface_for(box)

    QTest.keyClicks(box, "(painting:1.2)")
    process_events(app)

    assert box.toPlainText() == "(painting:1.2)"
    assert len(surface.projection_document().tokens) == 1
    assert first_emphasis_token(box).display_text == "painting"


def test_projection_surface_direct_weighted_emphasis_invalidates_raw_backing_fill(
    widgets: list[QWidget],
) -> None:
    """Completing a typed weighted shell should repaint stale raw backing text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=(
            "(small:1.20) breasts, flat chest, sparkling blue sash,\n"
            "sparkling blue bralette, (pale skin:1.20),\n\n"
        ),
        width=640,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(box.toPlainText()))
    box.setTextCursor(cursor)
    invalidated_rects: list[QRect] = []
    surface.backingFillInvalidated.connect(invalidated_rects.append)

    QTest.keyClicks(box, "(test:1.20)")
    process_events(app)

    assert box.toPlainText().endswith("(test:1.20)")
    assert first_emphasis_token(box).display_text == "small"
    assert surface.projection_document().tokens[-1].display_text == "test"
    assert invalidated_rects
    assert box.viewport().rect() in invalidated_rects


def test_projection_surface_typing_inline_decimal_emphasis_keeps_live_shells(
    widgets: list[QWidget],
) -> None:
    """Inline decimal emphasis should survive normalization when followed by plain text."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=260,
    )
    surface = surface_for(box)

    QTest.keyClicks(box, "(crescent:1.1) staff")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)

    assert box.toPlainText() == "(crescent:1.1) staff"
    assert len(surface.projection_document().tokens) == 1
    assert first_emphasis_token(box).display_text == "crescent"


def test_projection_surface_typing_inline_weight_shape_preserves_emphasis(
    widgets: list[QWidget],
) -> None:
    """Inline weighted groups should remain emphasis syntax while typing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=280,
    )
    surface = surface_for(box)

    QTest.keyClicks(box, "prefix (painting:1.2) suffix")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)

    assert box.toPlainText() == "prefix (painting:1.2) suffix"
    assert surface.projection_document().projection_text == (
        f"prefix {OBJECT_REPLACEMENT_CHARACTER}painting"
        f"{OBJECT_REPLACEMENT_CHARACTER} suffix"
    )
    assert len(surface.projection_document().tokens) == 1
    assert first_emphasis_token(box).display_text == "painting"


def test_projection_surface_keeps_raw_repaired_inline_emphasis_after_rich_typing(
    widgets: list[QWidget],
) -> None:
    """Raw-source emphasis repairs should survive later rich-mode typed edits."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"planted, staff, \(wooden:1.10\) staff, \(crescent:1.10\) staff",
        width=360,
    )
    surface = surface_for(box)

    box.setRichPromptRenderingEnabled(False)
    box.setSourceText("planted, staff, (wooden:1.10) staff, (crescent:1.10) staff")
    box.setRichPromptRenderingEnabled(True)
    QTest.keyClicks(box, ",")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)

    assert box.toPlainText() == (
        "planted, staff, (wooden:1.10) staff, (crescent:1.10) staff,"
    )
    assert len(surface.projection_document().tokens) == 2


def test_projection_surface_keeps_raw_unescaped_literal_after_rich_typing(
    widgets: list[QWidget],
) -> None:
    """Raw-source literal parenthesis choices should survive later rich typing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"painting \(medium\)",
        width=260,
    )

    box.setRichPromptRenderingEnabled(False)
    box.setSourceText("painting (medium)")
    box.setRichPromptRenderingEnabled(True)
    QTest.keyClicks(box, ",")
    process_events(app)

    assert box.toPlainText() == "painting (medium),"
