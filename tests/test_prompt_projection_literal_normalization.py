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

"""Tests for prompt projection literal normalization and rich paste behavior."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.projection.model import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionCaretPlacement,
    PromptProjectionTokenKind,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    first_emphasis_token,
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
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


def test_projection_surface_reclassifies_edited_literal_group_as_existing_emphasis_token(
    widgets: list[QWidget],
) -> None:
    """Typing a weight into an escaped literal should enter normal exact edit."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\)",
        width=240,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)

    token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1)"
    assert token.display_text == "test"
    assert token.value_text == "1"
    assert token.editing_value_text == "1"
    assert token.editing_caret_index == 1
    assert token.editing_select_all is False
    assert token.source_start < box.textCursor().position() < token.source_end

    focused_widget = QApplication.focusWidget()
    assert focused_widget is not None
    QTest.keyClicks(focused_widget, ".20")
    process_events(app)

    editing_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1)"
    assert editing_token.editing_value_text == "1.20"
    assert editing_token.editing_caret_index == 4

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    committed_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20)"
    assert committed_token.value_text == "1.20"
    assert committed_token.editing_value_text is None
    assert box.textCursor().position() == committed_token.source_end
    assert getattr(surface, "_cursor_state").placement is (
        PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE
    )


def test_projection_surface_space_after_auto_weight_moves_after_emphasis_token(
    widgets: list[QWidget],
) -> None:
    """Space after an auto-created weight should exit the token and insert after it."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\)",
        width=240,
    )
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1.20")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Space)
    process_events(app)

    token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20) "
    assert token.value_text == "1.20"
    assert token.editing_value_text is None
    assert box.textCursor().position() == len("(test:1.20) ")


def test_projection_surface_space_commits_active_auto_exact_weight_edit(
    widgets: list[QWidget],
) -> None:
    """Space should commit an active auto-created exact edit before inserting."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\)",
        width=240,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)
    focused_widget = QApplication.focusWidget()
    assert focused_widget is not None
    QTest.keyClicks(focused_widget, ".20")
    process_events(app)

    editing_token = first_emphasis_token(box)
    assert editing_token.editing_value_text == "1.20"

    QTest.keyClick(focused_widget, Qt.Key.Key_Space)
    process_events(app)

    committed_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20) "
    assert committed_token.value_text == "1.20"
    assert committed_token.editing_value_text is None
    assert box.textCursor().position() == len("(test:1.20) ")


def test_projection_surface_auto_exact_weight_edit_uses_existing_click_commit_flow(
    widgets: list[QWidget],
) -> None:
    """Auto-created exact weight edits should hide text caret and commit on outside click."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"\(test\), dog",
        width=260,
    )
    surface = surface_for(box)
    cursor = box.textCursor()
    cursor.setPosition(len(r"\(test"))
    box.setTextCursor(cursor)

    QTest.keyClicks(box, ":1")
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)
    focused_widget = QApplication.focusWidget()
    assert focused_widget is not None
    QTest.keyClicks(focused_widget, ".20")
    process_events(app)

    editing_token = first_emphasis_token(box)
    should_paint_caret = getattr(surface, "_should_paint_caret")
    assert box.toPlainText() == "(test:1), dog"
    assert editing_token.editing_value_text == "1.20"
    assert not should_paint_caret()

    token_rect = surface.token_anchor_rect(editing_token)
    assert token_rect is not None
    click_point = QPoint(int(token_rect.right() + 18), int(token_rect.center().y()))
    QTest.mouseClick(box.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
    process_events(app, cycles=4)

    committed_token = first_emphasis_token(box)
    assert box.toPlainText() == "(test:1.20), dog"
    assert committed_token.value_text == "1.20"
    assert committed_token.editing_value_text is None


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


def test_projection_surface_paste_preserves_existing_raw_unescaped_literal(
    widgets: list[QWidget],
) -> None:
    """Rich paste should normalize pasted text without rewriting existing source."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=320,
    )
    box.setSourceText("painting (medium), ")
    box.setFocus()
    QApplication.clipboard().setText("blue (butterfly) bow, red (gem:1.10)")

    box.paste()
    process_events(app)

    assert box.toPlainText() == (
        "painting (medium), blue (butterfly:1.10) bow, red (gem:1.10)"
    )


def test_prompt_editor_paste_projects_rich_tokens_immediately(
    widgets: list[QWidget],
) -> None:
    """Pasted weighted prompt syntax should render without waiting for later typing."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="",
        width=420,
    )
    surface = surface_for(box)
    QApplication.clipboard().setText(
        "\n".join(
            (
                "best quality, score_7, ppw, masterpiece,",
                "",
                "planted, staff, (wooden:1.10) staff, (crescent:1.10) staff,",
                "",
                "(pink and blue:1.10) witch outfit, (blue accents:1.10),",
                "",
                "<lora:Anima\\style\\PeopleWorks:1.00>",
            )
        )
    )

    box.paste()
    process_events(app, cycles=1)

    assert box.toPlainText() == (
        "best quality, score_7, ppw, masterpiece,\n"
        "\n"
        "planted, staff, (wooden:1.10) staff, (crescent:1.10) staff,\n"
        "\n"
        "(pink and blue:1.10) witch outfit, (blue accents:1.10),\n"
        "\n"
        "<lora:Anima\\style\\PeopleWorks:1.00>"
    )
    assert [
        token.display_text
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ] == [
        "wooden",
        "crescent",
        "pink and blue",
        "blue accents",
    ]


def test_prompt_editor_shortcut_paste_projects_rich_tokens_immediately(
    widgets: list[QWidget],
) -> None:
    """Shortcut paste should render weighted prompt syntax synchronously."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="old prompt",
        width=420,
    )
    surface = surface_for(box)
    QApplication.clipboard().setText(
        "\n".join(
            (
                "best quality, score_7, ppw, masterpiece,",
                "",
                "planted, staff, (wooden:1.10) staff, (crescent:1.10) staff,",
                "",
                "(pink and blue:1.10) witch outfit, (blue accents:1.10),",
                "",
                "<lora:Anima\\style\\PeopleWorks:1.00>",
            )
        )
    )
    box.setFocus()
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(box, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

    assert box.toPlainText() == (
        "best quality, score_7, ppw, masterpiece,\n"
        "\n"
        "planted, staff, (wooden:1.10) staff, (crescent:1.10) staff,\n"
        "\n"
        "(pink and blue:1.10) witch outfit, (blue accents:1.10),\n"
        "\n"
        "<lora:Anima\\style\\PeopleWorks:1.00>"
    )
    assert [
        token.display_text
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ] == [
        "wooden",
        "crescent",
        "pink and blue",
        "blue accents",
    ]


def test_prompt_editor_shortcut_paste_same_text_keeps_rich_tokens_immediately(
    widgets: list[QWidget],
) -> None:
    """Shortcut paste over an identical full selection should keep rich projection."""

    app = ensure_qapp()
    prompt = "\n".join(
        (
            "best quality, score_7, ppw, masterpiece,",
            "",
            "planted, staff, (wooden:1.10) staff, (crescent:1.10) staff,",
            "",
            "(pink and blue:1.10) witch outfit, (blue accents:1.10),",
            "",
            "<lora:Anima\\style\\PeopleWorks:1.00>",
        )
    )
    box = show_prompt_editor(
        widgets,
        text=prompt,
        width=420,
    )
    surface = surface_for(box)
    flush_semantic_refresh(box)
    flush_projection_update_scheduler(surface)
    process_events(app)

    assert [
        token.display_text
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ] == [
        "wooden",
        "crescent",
        "pink and blue",
        "blue accents",
    ]

    box.setFocus()
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(box, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(box, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

    assert box.toPlainText() == prompt
    assert [
        token.display_text
        for token in surface.projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    ] == [
        "wooden",
        "crescent",
        "pink and blue",
        "blue accents",
    ]
