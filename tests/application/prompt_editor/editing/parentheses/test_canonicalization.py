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

"""Contracts for pure prompt parenthesis canonicalization."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor.editing.literal_parentheses import (
    PromptParenthesisTransitionKind,
    canonicalize_prompt_parentheses,
)


def test_explicit_numeric_emphasis_has_no_magnitude_heuristic() -> None:
    """Preserve every parsed explicit numeric weight regardless of magnitude."""

    assert canonicalize_prompt_parentheses("(wide shot:6)").text == "(wide shot:6)"
    assert canonicalize_prompt_parentheses("(wide shot:1999)").text == (
        "(wide shot:1999)"
    )
    assert canonicalize_prompt_parentheses("(wide shot:0.01)").text == (
        "(wide shot:0.01)"
    )


def test_unknown_implicit_emphasis_is_stabilized_with_exact_nesting_weight() -> None:
    """Rewrite implicit ComfyUI nesting without losing deeper precision."""

    assert canonicalize_prompt_parentheses("(blue laces)").text == ("(blue laces:1.10)")
    assert canonicalize_prompt_parentheses("((blue laces))").text == (
        "(blue laces:1.21)"
    )
    assert canonicalize_prompt_parentheses("(((blue laces)))").text == (
        "(blue laces:1.331)"
    )


def test_canonicalizer_emits_authoritative_transitions_and_boundaries() -> None:
    """Carry semantic rewrites and cursor mappings in one result owner."""

    result = canonicalize_prompt_parentheses("alpha, ((blue laces))")

    assert result.text == "alpha, (blue laces:1.21)"
    assert result.boundary_positions[0] == 0
    assert result.boundary_positions[-1] == len(result.text)
    assert [transition.kind for transition in result.transitions] == [
        PromptParenthesisTransitionKind.IMPLICIT_EMPHASIS
    ]
    assert result.transitions[0].nesting_depth == 2


def test_nested_implicit_group_inside_explicit_emphasis_is_stabilized() -> None:
    """Preserve an authored outer weight while making inner nesting explicit."""

    assert (
        canonicalize_prompt_parentheses("outer (blue (butterfly) bow:1.20)").text
        == "outer (blue (butterfly:1.10) bow:1.20)"
    )


@pytest.mark.parametrize(
    "source",
    (
        '"(quoted)"',
        "don't (stop)",
        r"already \(literal\)",
        "unbalanced (group",
    ),
)
def test_structural_scanner_respects_quotes_escapes_and_unbalanced_groups(
    source: str,
) -> None:
    """Keep quoted, escaped, and incomplete structures tolerant and predictable."""

    result = canonicalize_prompt_parentheses(source).text

    if source == "don't (stop)":
        assert result == "don't (stop:1.10)"
    else:
        assert result == source
