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

"""Contract tests for reusable inline-completion suffix matching."""

from __future__ import annotations

from substitute.presentation.widgets.inline_completion import inline_completion_suffix


def test_inline_completion_exact_prefix_returns_suffix() -> None:
    """A matching prefix should return the remaining candidate text."""

    assert (
        inline_completion_suffix(
            typed_text="aman",
            candidate_text="amanatsuIllustrious_v11",
        )
        == "atsuIllustrious_v11"
    )


def test_inline_completion_is_case_insensitive_and_preserves_candidate_case() -> None:
    """Matching should ignore case while returning the original-cased suffix."""

    assert (
        inline_completion_suffix(
            typed_text="t-noob",
            candidate_text="T-noobnai3 - v9",
        )
        == "nai3 - v9"
    )


def test_inline_completion_empty_query_returns_no_suffix() -> None:
    """Empty text should not show a ghost completion."""

    assert inline_completion_suffix(typed_text="", candidate_text="Alpha") == ""


def test_inline_completion_overlong_query_returns_no_suffix() -> None:
    """Typed text longer than the candidate cannot be completed."""

    assert inline_completion_suffix(typed_text="Alphabet", candidate_text="Alpha") == ""


def test_inline_completion_mismatched_prefix_returns_no_suffix() -> None:
    """Non-prefix substring matches should not produce ghost text."""

    assert (
        inline_completion_suffix(typed_text="v9", candidate_text="T-noobnai3 - v9")
        == ""
    )


def test_inline_completion_equivalence_is_opt_in() -> None:
    """Equivalent characters should only match when configured."""

    assert (
        inline_completion_suffix(
            typed_text="T noob",
            candidate_text="T_noobnai3",
        )
        == ""
    )
    assert (
        inline_completion_suffix(
            typed_text="T noob",
            candidate_text="T_noobnai3",
            equivalent_characters=(frozenset({" ", "_"}),),
        )
        == "nai3"
    )


def test_inline_completion_separator_equivalence_is_opt_in() -> None:
    """Path separator equivalence should be configurable by callers."""

    assert (
        inline_completion_suffix(
            typed_text=r"Illustrious\aman",
            candidate_text="Illustrious/amanatsu",
        )
        == ""
    )
    assert (
        inline_completion_suffix(
            typed_text=r"Illustrious\aman",
            candidate_text="Illustrious/amanatsu",
            equivalent_characters=(frozenset({"/", "\\"}),),
        )
        == "atsu"
    )
