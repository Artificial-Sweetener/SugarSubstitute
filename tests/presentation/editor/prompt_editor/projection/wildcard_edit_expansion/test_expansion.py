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

"""Verify wildcard edit expansion decisions independently of Qt geometry."""

from __future__ import annotations

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.projection.wildcard_edit_expansion import (
    PromptWildcardEditExpansion,
)


def test_wildcard_edit_expansion_preserves_selection_inside_new_token() -> None:
    """Semantic catch-up must keep a wildcard raw around its live source caret."""

    document = PromptDocumentService().build_document_view("1girl, {hair}, black dress")
    session = PromptProjectionSession()

    expanded = PromptWildcardEditExpansion(session).preserve_editable_selection(
        document,
        selection_start=12,
        selection_end=12,
    )

    assert expanded is True
    assert session.expanded_source_range == (7, 13)


def test_wildcard_edit_expansion_leaves_boundary_caret_collapsed() -> None:
    """A caret after a completed wildcard must preserve its compact projection."""

    document = PromptDocumentService().build_document_view("1girl, {hair}, black dress")
    session = PromptProjectionSession()

    expanded = PromptWildcardEditExpansion(session).preserve_editable_selection(
        document,
        selection_start=13,
        selection_end=13,
    )

    assert expanded is False
    assert session.expanded_source_range is None
