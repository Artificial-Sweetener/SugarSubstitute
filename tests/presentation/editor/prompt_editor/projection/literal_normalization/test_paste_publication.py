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

"""Verify pasted literals and rich tokens publish immediately."""

from __future__ import annotations

import pytest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

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
    flush_projection_update_scheduler,
    flush_semantic_refresh,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


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
