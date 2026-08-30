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

"""Contracts for tag-aware prompt parenthesis edit normalization."""

from __future__ import annotations


from substitute.application.ports import PromptTagLexiconSnapshot
from substitute.application.prompt_editor.editing.literal_parentheses import (
    PromptParenthesisTransitionKind,
)
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)


def test_known_tag_parentheses_are_escaped_from_prepared_snapshot() -> None:
    """Escape a literal only when exact prepared tag knowledge identifies it."""

    snapshot = PromptTagLexiconSnapshot(
        normalized_tags=frozenset({"vertin (reverse:1999)"})
    )
    service = PromptSourceNormalizationService(tag_snapshot=snapshot)

    assert service.normalize_for_paste("vertin (reverse:1999)").text == (
        r"vertin \(reverse:1999\)"
    )
    assert service.normalize_for_paste("unknown (reverse:1999)").text == (
        "unknown (reverse:1999.00)"
    )


def test_typed_large_integer_reclassifies_escaped_group_as_emphasis() -> None:
    """Re-evaluate an auto-owned literal when typed syntax becomes explicit."""

    source = r"\(wide shot:6\)"
    service = PromptSourceNormalizationService()
    result = service.normalize_for_typed_edit_range(
        source,
        start=12,
        end=13,
        replacement_text="6",
    )

    assert result.text == "(wide shot:6)"
    assert result.transitions[0].kind is (
        PromptParenthesisTransitionKind.ESCAPED_LITERAL_TO_EMPHASIS
    )


def test_typed_known_tag_re_evaluates_complete_segment() -> None:
    """Use the whole segment for exact tag recognition when its paren closes."""

    snapshot = PromptTagLexiconSnapshot(
        normalized_tags=frozenset({"vertin (reverse:1999)"})
    )
    service = PromptSourceNormalizationService(tag_snapshot=snapshot)
    source = "vertin (reverse:1999)"

    result = service.normalize_for_typed_edit_range(
        source,
        start=len(source) - 1,
        end=len(source),
        replacement_text=")",
    )

    assert result.text == r"vertin \(reverse:1999\)"
