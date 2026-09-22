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

"""Choose canonical prompt text wrapping boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont

from substitute.presentation.editor.prompt_editor.layout.text_measurement import (
    PROMPT_LAYOUT_WIDTH_EPSILON,
    PromptTextMeasurementCache,
)

_WORD_JOINING_CHARACTERS = frozenset(("_", "-", "'"))


@dataclass(frozen=True, slots=True)
class PromptTextBreakDecision:
    """Describe an accepted text break after enforcing word integrity."""

    consumed_length: int
    break_before_text: bool = False


def visible_wrap_candidate_length(
    text: str,
    *,
    candidate_length: int,
    available_width: float,
    font: QFont,
    measurement_cache: PromptTextMeasurementCache,
) -> int:
    """Return the longest wrap candidate with a visible cursor boundary.

    ``QTextLine.textLength()`` can retain trailing whitespace after its natural
    width fits the line. The caret still advances through that whitespace, so
    canonical layout moves it when its boundary exceeds the available width.
    Measure the unwrapped boundary because Qt's wrapped-line cursor geometry
    excludes some trailing whitespace that the editor must still reveal.
    """

    bounded_length = min(
        max(1, candidate_length),
        len(text),
    )
    boundary_offsets = measurement_cache.unwrapped_text_offsets(text, font)
    if (
        boundary_offsets[bounded_length]
        <= available_width + PROMPT_LAYOUT_WIDTH_EPSILON
    ):
        return bounded_length
    return max(
        (
            index
            for index in range(1, bounded_length + 1)
            if boundary_offsets[index] <= available_width + PROMPT_LAYOUT_WIDTH_EPSILON
        ),
        default=0,
    )


def adjust_break_for_word_integrity(
    text: str,
    *,
    consumed_cluster_length: int,
    candidate_length: int,
    line_has_content: bool,
    font: QFont,
    content_width: float,
    measurement_cache: PromptTextMeasurementCache,
) -> PromptTextBreakDecision:
    """Return a break decision that splits only oversized words."""

    remaining_length = len(text) - consumed_cluster_length
    candidate_length = min(max(1, candidate_length), remaining_length)
    candidate_break = consumed_cluster_length + candidate_length
    word_span = _word_span_at_break(text, candidate_break)
    if word_span is None:
        return PromptTextBreakDecision(consumed_length=candidate_length)

    word_start, word_end = word_span
    if not measurement_cache.word_fits_content_width(
        text[word_start:word_end],
        font=font,
        content_width=content_width,
    ):
        return PromptTextBreakDecision(consumed_length=candidate_length)

    if word_start <= consumed_cluster_length:
        if line_has_content:
            return PromptTextBreakDecision(consumed_length=0, break_before_text=True)
        return PromptTextBreakDecision(
            consumed_length=max(1, word_end - consumed_cluster_length)
        )

    prefix_before_word = text[consumed_cluster_length:word_start]
    if prefix_before_word.strip():
        return PromptTextBreakDecision(
            consumed_length=word_start - consumed_cluster_length
        )
    if line_has_content and prefix_before_word:
        return PromptTextBreakDecision(
            consumed_length=word_start - consumed_cluster_length
        )
    if line_has_content:
        return PromptTextBreakDecision(consumed_length=0, break_before_text=True)
    return PromptTextBreakDecision(consumed_length=word_end - consumed_cluster_length)


def _word_span_at_break(text: str, break_index: int) -> tuple[int, int] | None:
    """Return the whole word around one intra-word break candidate."""

    if break_index <= 0 or break_index >= len(text):
        return None
    if not (
        _is_word_wrap_character(text[break_index - 1])
        and _is_word_wrap_character(text[break_index])
    ):
        return None
    word_start = break_index - 1
    while word_start > 0 and _is_word_wrap_character(text[word_start - 1]):
        word_start -= 1
    word_end = break_index + 1
    while word_end < len(text) and _is_word_wrap_character(text[word_end]):
        word_end += 1
    return (word_start, word_end)


def _is_word_wrap_character(character: str) -> bool:
    """Return whether one character belongs to an unbreakable prompt word."""

    return character.isalnum() or character in _WORD_JOINING_CHARACTERS


__all__ = [
    "PromptTextBreakDecision",
    "adjust_break_for_word_integrity",
    "visible_wrap_candidate_length",
]
