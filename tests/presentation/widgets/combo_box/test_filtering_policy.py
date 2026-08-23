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

"""Verify searchable-combo filtering policy."""

from __future__ import annotations

from substitute.presentation.widgets.searchable_combo_helpers import (
    filtered_combo_indexes,
)


def test_empty_query_keeps_every_item_visible() -> None:
    """Keep the complete item inventory when no search term is supplied."""

    assert filtered_combo_indexes(["Alpha", "Beta"], "") == [0, 1]


def test_prefix_matches_rank_before_substrings() -> None:
    """Rank prefix matches ahead of later substring matches."""

    items = ["The Beta Model", "beta scheduler", "alphabet soup"]

    assert filtered_combo_indexes(items, "beta") == [1, 0]


def test_matching_uses_case_insensitive_substrings() -> None:
    """Find normalized search terms within longer item labels."""

    items = ["Euler Normal", "DPM++ 2M Karras", "Heun"]

    assert filtered_combo_indexes(items, "karr") == [1]


def test_unmatched_query_returns_no_indexes() -> None:
    """Return no choices when the query matches no item."""

    assert filtered_combo_indexes(["Euler", "Heun"], "missing") == []
