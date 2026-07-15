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

"""Contract tests for duplicate-segment diagnostic source edits."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptDiagnosticTextEdit,
    PromptDuplicateSegmentDiagnosticPayload,
    emphasize_first_duplicate_segment_edits,
    remove_duplicate_segment_edits,
)


def test_remove_duplicate_from_middle_segment() -> None:
    """Removing a middle duplicate should clean the following separator."""

    text = "alpha, beta, gamma"
    payload = _payload(first_start=0, first_end=5, duplicate_start=7, duplicate_end=11)

    assert _apply(text, remove_duplicate_segment_edits(text, payload)) == (
        "alpha, gamma"
    )


def test_remove_duplicate_from_end_segment() -> None:
    """Removing a trailing duplicate should clean the preceding separator."""

    text = "alpha, beta"
    payload = _payload(first_start=0, first_end=5, duplicate_start=7, duplicate_end=11)

    assert _apply(text, remove_duplicate_segment_edits(text, payload)) == "alpha"


def test_remove_duplicate_from_start_segment() -> None:
    """Removing a leading diagnostic should clean the following separator."""

    text = "alpha, beta"
    payload = _payload(first_start=7, first_end=11, duplicate_start=0, duplicate_end=5)

    assert _apply(text, remove_duplicate_segment_edits(text, payload)) == "beta"


def test_emphasize_first_wraps_plain_first_occurrence() -> None:
    """A plain first segment should become weighted emphasis at 1.10."""

    text = "yellow hat, yellow hat"
    payload = _payload(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=10,
        duplicate_start=12,
        duplicate_end=22,
    )

    assert _apply(text, emphasize_first_duplicate_segment_edits(text, payload)) == (
        "(yellow hat:1.10)"
    )


def test_emphasize_first_increments_weighted_first_occurrence() -> None:
    """A weighted first segment should increase by the base 0.10."""

    text = "(yellow hat:1.20), yellow hat"
    payload = _payload(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=17,
        duplicate_start=19,
        duplicate_end=29,
    )

    assert _apply(text, emphasize_first_duplicate_segment_edits(text, payload)) == (
        "(yellow hat:1.30)"
    )


def test_emphasize_first_transfers_positive_duplicate_weight() -> None:
    """A weighted duplicate should contribute its above-neutral weight."""

    text = "(yellow hat:1.20), (yellow hat:1.10)"
    payload = _payload(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=17,
        duplicate_start=19,
        duplicate_end=36,
    )

    assert _apply(text, emphasize_first_duplicate_segment_edits(text, payload)) == (
        "(yellow hat:1.40)"
    )


def test_emphasize_first_transfers_duplicate_weight_to_plain_first() -> None:
    """A plain first segment should receive the base and duplicate extra weight."""

    text = "yellow hat, (yellow hat:1.30)"
    payload = _payload(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=10,
        duplicate_start=12,
        duplicate_end=29,
    )

    assert _apply(text, emphasize_first_duplicate_segment_edits(text, payload)) == (
        "(yellow hat:1.40)"
    )


def test_emphasize_first_ignores_below_neutral_duplicate_weight() -> None:
    """Below-neutral duplicate emphasis should not reduce the kept segment."""

    text = "(yellow hat:1.20), (yellow hat:0.90)"
    payload = _payload(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=17,
        duplicate_start=19,
        duplicate_end=36,
    )

    assert _apply(text, emphasize_first_duplicate_segment_edits(text, payload)) == (
        "(yellow hat:1.30)"
    )


def test_emphasize_first_keeps_first_segment_text_for_underscore_duplicate() -> None:
    """Wrapping should preserve the first segment's visible spelling."""

    text = "yellow hat, yellow_hat"
    payload = _payload(
        normalized_segment="yellow hat",
        first_start=0,
        first_end=10,
        duplicate_start=12,
        duplicate_end=22,
    )

    assert _apply(text, emphasize_first_duplicate_segment_edits(text, payload)) == (
        "(yellow hat:1.10)"
    )


def _payload(
    *,
    first_start: int,
    first_end: int,
    duplicate_start: int,
    duplicate_end: int,
    normalized_segment: str = "alpha",
) -> PromptDuplicateSegmentDiagnosticPayload:
    """Return one duplicate-segment payload for mutation tests."""

    return PromptDuplicateSegmentDiagnosticPayload(
        normalized_segment=normalized_segment,
        first_source_start=first_start,
        first_source_end=first_end,
        duplicate_source_start=duplicate_start,
        duplicate_source_end=duplicate_end,
    )


def _apply(text: str, edits: tuple[PromptDiagnosticTextEdit, ...]) -> str:
    """Apply source edits from highest start to lowest start."""

    result = text
    for edit in sorted(edits, key=lambda item: item.source_start, reverse=True):
        result = (
            result[: edit.source_start]
            + edit.replacement_text
            + result[edit.source_end :]
        )
    return result
