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

"""Tests for parser-backed prompt weight source normalization."""

from __future__ import annotations

from substitute.domain.prompt import normalize_prompt_weights


def test_normalize_prompt_weights_formats_emphasis_weights() -> None:
    """Emphasis weights should use fixed two-decimal source text."""

    assert normalize_prompt_weights("(cat:1)").text == "(cat:1.00)"
    assert normalize_prompt_weights("(cat:0.9)").text == "(cat:0.90)"
    assert normalize_prompt_weights("(cat:0.90)").text == "(cat:0.90)"


def test_normalize_prompt_weights_formats_lora_weights() -> None:
    """LoRA schedule weights should use fixed two-decimal source text."""

    assert normalize_prompt_weights("<lora:Name:1>").text == "<lora:Name:1.00>"
    assert normalize_prompt_weights("<lora:Name:0.9>").text == "<lora:Name:0.90>"
    assert normalize_prompt_weights("<lora:Name:0.9:1>").text == "<lora:Name:0.90:1.00>"


def test_normalize_prompt_weights_rewrites_multiple_weights_in_one_pass() -> None:
    """Multiple parsed weight ranges should account for cumulative length changes."""

    source = "(cat:1), <lora:Name:0.9:1>, (dog:0.90)"

    normalized = normalize_prompt_weights(source)

    assert normalized.text == "(cat:1.00), <lora:Name:0.90:1.00>, (dog:0.90)"
    assert normalized.boundary_positions[0] == 0
    assert normalized.boundary_positions[len(source)] == len(normalized.text)


def test_normalize_prompt_weights_leaves_invalid_or_plain_text_unchanged() -> None:
    """Only parser-recognized weight ranges should be normalized."""

    source = "1, (cat:abc), <lora:Name:>, <lora:Name:abc>"

    normalized = normalize_prompt_weights(source)

    assert normalized.text == source
    assert normalized.boundary_positions == tuple(range(len(source) + 1))


def test_normalize_prompt_weights_preserves_neutral_emphasis_shell() -> None:
    """Paste normalization should not apply emphasis-control neutral unwrapping."""

    assert normalize_prompt_weights("(cat:1)").text == "(cat:1.00)"


def test_normalize_prompt_weights_maps_boundaries_after_replacements() -> None:
    """Boundary mapping should include cumulative deltas from normalized weights."""

    source = "(cat:1), <lora:Name:0.9>"
    normalized = normalize_prompt_weights(source)

    first_weight_end = source.index(")")  # after the original emphasis weight.
    second_weight_end = source.index(">")

    assert normalized.text == "(cat:1.00), <lora:Name:0.90>"
    assert normalized.boundary_positions[first_weight_end] == len("(cat:1.00")
    assert normalized.boundary_positions[second_weight_end] == len(
        "(cat:1.00), <lora:Name:0.90"
    )
