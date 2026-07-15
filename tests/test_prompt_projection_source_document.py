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

"""Guard the projection source-document mirror owner."""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QFont, QTextDocument, QTextOption
from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor.projection.source_change_applier import (
    PromptProjectionSourceDocumentRangeEdit,
)
from substitute.presentation.editor.prompt_editor.projection.source_document import (
    PromptProjectionSourceDocument,
)


def _app() -> QApplication:
    """Return a QApplication for QTextDocument behavior checks."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def test_source_document_initial_setup_matches_surface_contract() -> None:
    """The adapter should create the live Qt document with editor defaults."""

    _app()
    source_document = PromptProjectionSourceDocument()
    document = source_document.document()

    assert isinstance(document, QTextDocument)
    assert source_document.document() is document
    assert document.documentMargin() == 4.0
    assert document.isUndoRedoEnabled() is False
    assert (
        document.defaultTextOption().wrapMode()
        is QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
    )


def test_source_document_syncs_default_font_by_copy() -> None:
    """Default-font sync should copy the widget font and preserve repeat no-ops."""

    _app()
    source_document = PromptProjectionSourceDocument()
    font = QFont("Courier New", 12)

    source_document.sync_default_font(font)
    first_default_font = QFont(source_document.document().defaultFont())
    source_document.sync_default_font(font)
    second_default_font = QFont(source_document.document().defaultFont())
    font.setPointSize(18)

    assert first_default_font == second_default_font
    assert source_document.document().defaultFont() == first_default_font


def test_source_document_syncs_text_width_for_wrapping() -> None:
    """Text width changes should be delegated to the owned QTextDocument."""

    _app()
    source_document = PromptProjectionSourceDocument()

    source_document.sync_text_width(243.5)

    assert source_document.document().textWidth() == 243.5


def test_source_document_replaces_full_text_exactly() -> None:
    """Full replacement should keep the Qt mirror exactly equal to source text."""

    _app()
    source_document = PromptProjectionSourceDocument()

    source_document.replace_text("alpha\nbeta")

    assert source_document.document().toPlainText() == "alpha\nbeta"


def test_source_document_applies_single_character_insertion_range_edit() -> None:
    """A single-character insertion should mutate the live document in place."""

    _app()
    source_document = PromptProjectionSourceDocument()
    source_document.replace_text("cat")

    applied = source_document.apply_range_edit(
        PromptProjectionSourceDocumentRangeEdit(
            previous_text="cat",
            next_text="cart",
            start=2,
            end=2,
            replacement_text="r",
        )
    )

    assert applied is True
    assert source_document.document().toPlainText() == "cart"


def test_source_document_applies_single_character_deletion_range_edit() -> None:
    """A single-character deletion should mutate the live document in place."""

    _app()
    source_document = PromptProjectionSourceDocument()
    source_document.replace_text("cart")

    applied = source_document.apply_range_edit(
        PromptProjectionSourceDocumentRangeEdit(
            previous_text="cart",
            next_text="cat",
            start=2,
            end=3,
            replacement_text="",
        )
    )

    assert applied is True
    assert source_document.document().toPlainText() == "cat"


def test_source_document_rejects_unsafe_range_edit_without_mutation() -> None:
    """An unsafe bounded edit should report failure and leave text untouched."""

    _app()
    source_document = PromptProjectionSourceDocument()
    source_document.replace_text("alpha")

    applied = source_document.apply_range_edit(
        PromptProjectionSourceDocumentRangeEdit(
            previous_text="wrong",
            next_text="alpha!",
            start=5,
            end=5,
            replacement_text="!",
        )
    )

    assert applied is False
    assert source_document.document().toPlainText() == "alpha"


def test_source_document_falls_back_to_full_replacement_for_large_edit() -> None:
    """The surface-facing mirror method should preserve text parity on fallback."""

    _app()
    source_document = PromptProjectionSourceDocument()
    source_document.replace_text("alpha")

    used_range_edit = source_document.replace_with_range_fallback(
        next_text="alpha beta",
        previous_text="alpha",
        start=5,
        end=5,
        replacement_text=" beta",
    )

    assert used_range_edit is False
    assert source_document.document().toPlainText() == "alpha beta"


def test_source_document_prefers_range_edit_when_fallback_is_unneeded() -> None:
    """The surface-facing mirror method should use safe bounded edits directly."""

    _app()
    source_document = PromptProjectionSourceDocument()
    source_document.replace_text("alpha")

    used_range_edit = source_document.replace_with_range_fallback(
        next_text="alphas",
        previous_text="alpha",
        start=5,
        end=5,
        replacement_text="s",
    )

    assert used_range_edit is True
    assert source_document.document().toPlainText() == "alphas"


def test_source_document_fallback_preserves_exact_text_when_previous_text_is_stale() -> (
    None
):
    """A stale previous text should still leave the mirror equal to next text."""

    _app()
    source_document = PromptProjectionSourceDocument()
    source_document.replace_text("current")

    used_range_edit = source_document.replace_with_range_fallback(
        next_text="current!",
        previous_text="stale",
        start=5,
        end=5,
        replacement_text="!",
    )

    assert used_range_edit is False
    assert source_document.document().toPlainText() == "current!"
