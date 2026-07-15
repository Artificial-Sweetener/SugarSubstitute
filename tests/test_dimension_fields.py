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

"""Contract tests for dimension-field pair inference."""

from __future__ import annotations

from substitute.domain.node_behavior.dimension_fields import (
    DimensionFieldPair,
    infer_dimension_field_groups,
    infer_dimension_field_pairs,
)


def test_infer_dimension_field_pairs_matches_unqualified_width_height() -> None:
    """Unqualified width and height fields should form the root dimension pair."""

    assert infer_dimension_field_pairs(("width", "height")) == (
        DimensionFieldPair(stem="", width_key="width", height_key="height"),
    )


def test_infer_dimension_field_pairs_matches_shared_stems() -> None:
    """Matching source and target stems should each form independent pairs."""

    assert infer_dimension_field_pairs(
        ("source_width", "source_height", "target_width", "target_height")
    ) == (
        DimensionFieldPair(
            stem="source",
            width_key="source_width",
            height_key="source_height",
        ),
        DimensionFieldPair(
            stem="target",
            width_key="target_width",
            height_key="target_height",
        ),
    )


def test_infer_dimension_field_pairs_rejects_mixed_or_partial_pairs() -> None:
    """Different stems and one-sided dimensions should not form pairs."""

    assert infer_dimension_field_pairs(("source_width", "target_height")) == ()
    assert infer_dimension_field_pairs(("width", "target_height")) == ()
    assert infer_dimension_field_pairs(("source_width",)) == ()


def test_infer_dimension_field_pairs_preserves_pair_discovery_order() -> None:
    """Pairs should be ordered by the first participating field in input order."""

    assert infer_dimension_field_pairs(
        ("target_height", "source_width", "target_width", "source_height")
    ) == (
        DimensionFieldPair(
            stem="target",
            width_key="target_width",
            height_key="target_height",
        ),
        DimensionFieldPair(
            stem="source",
            width_key="source_width",
            height_key="source_height",
        ),
    )


def test_infer_dimension_field_groups_skips_occupied_fields() -> None:
    """Dimension groups should not reuse fields already owned by another group."""

    assert infer_dimension_field_groups(
        ("width", "height", "source_width", "source_height"),
        occupied_fields=frozenset({"width"}),
    ) == (("source_width", "source_height"),)
