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

"""Service-level tests for the prompt editor application layer."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import (
    PromptDocumentService,
)


def test_prompt_document_service_hides_literal_parenthesis_escapes_in_segment_views() -> (
    None
):
    """Document views should expose user-facing segment labels without protective backslashes."""

    document_service = PromptDocumentService()

    document_view = document_service.build_document_view(r"painting \(medium\)")

    assert document_view.source_text == r"painting \(medium\)"
    assert [segment.text for segment in document_view.segments] == [
        r"painting \(medium\)"
    ]
    assert [segment.display_text for segment in document_view.segments] == [
        "painting (medium)"
    ]


def test_prompt_document_service_hides_literal_parenthesis_escapes_in_reorder_chips() -> (
    None
):
    """Reorder chip labels should show literal parenthetical text without raw escapes."""

    document_service = PromptDocumentService()

    chips = document_service.reorder_chips(
        document_service.build_document_view(r"vertin \(reverse:1999\)")
    )

    assert [chip.text for chip in chips] == [r"vertin \(reverse:1999\)"]
    assert [chip.display_text for chip in chips] == ["vertin (reverse:1999)"]
