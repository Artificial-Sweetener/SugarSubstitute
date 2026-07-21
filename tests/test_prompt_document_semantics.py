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

"""Verify prompt document coordinate ownership and scalable identity mapping."""

from substitute.application.prompt_editor.prompt_document_semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptIdentityCharacterRangeSequence,
)
from substitute.domain.prompt import SourceRange


def test_ordinary_prompt_mapping_keeps_large_identity_coordinates_lazy() -> None:
    """Ordinary prompts should not allocate one coordinate object per character."""

    source_text = "tag, " * 20_000

    mapping = OrdinaryPromptDocumentSemantics().value_mappings_for_text(source_text)[0]

    assert isinstance(
        mapping.logical_character_ranges,
        PromptIdentityCharacterRangeSequence,
    )
    assert len(mapping.logical_character_ranges) == len(source_text)
    assert mapping.logical_character_ranges[25] == SourceRange(25, 26)
    assert mapping.source_range_for_logical_range(SourceRange(25, 40)) == SourceRange(
        25,
        40,
    )
    assert mapping.logical_range_for_source_range(SourceRange(25, 40)) == SourceRange(
        25,
        40,
    )
