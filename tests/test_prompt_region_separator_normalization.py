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

"""Contract tests for bounded canonical regional-separator normalization."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)


@pytest.mark.parametrize(
    ("text", "start", "end", "replacement_text", "expected", "caret"),
    [
        ("global[SEP]regional", 10, 11, "]", "global\n[SEP]\nregional", 13),
        ("global\n[SEP]regional", 11, 12, "]", "global\n[SEP]\nregional", 13),
        ("global[SEP]\nregional", 10, 11, "]", "global\n[SEP]\nregional", 13),
        ("[SEP]", 4, 5, "]", "[SEP]\n", 6),
    ],
)
def test_typed_separator_completion_normalizes_its_bounded_line_context(
    text: str,
    start: int,
    end: int,
    replacement_text: str,
    expected: str,
    caret: int,
) -> None:
    """Completing a marker should place it on one line and remap the caret once."""

    normalization = PromptSourceNormalizationService().normalize_for_typed_edit_range(
        text,
        start=start,
        end=end,
        replacement_text=replacement_text,
    )

    assert normalization.text == expected
    assert normalization.boundary_positions[end] == caret


def test_paste_normalization_canonicalizes_only_markers_in_the_inserted_range() -> None:
    """Pasted markers should gain line boundaries without rewriting unrelated source."""

    text = "α before  [sep]  βglobal[SEP]regional終"
    paste_start = text.index("global")

    normalization = PromptSourceNormalizationService().normalize_for_paste_range(
        text,
        start=paste_start,
        end=len(text) - 1,
    )

    assert normalization.text == "α before  [sep]  βglobal\n[SEP]\nregional終"


def test_typed_malformed_separator_remains_ordinary_source() -> None:
    """Partial and lowercase markers should remain directly editable text."""

    service = PromptSourceNormalizationService()

    for text in ("global[SEP", "globalSEP]", "global[sep]"):
        normalization = service.normalize_for_typed_edit_range(
            text,
            start=len(text),
            end=len(text),
            replacement_text="",
        )
        assert normalization.text == text


@pytest.mark.parametrize(
    ("text", "position", "expected"),
    (
        ("global\n[SEP]pink", len("global\n[SEP]"), "global\n[SEP]\npink"),
        ("global[SEP]\npink", len("global"), "global\n[SEP]\npink"),
        ("global\r\n[SEP]pink", len("global\r\n[SEP]"), "global\r\n[SEP]\r\npink"),
    ),
)
def test_typed_deletion_restores_complete_separator_line_boundaries(
    text: str,
    position: int,
    expected: str,
) -> None:
    """A deletion may expose malformed marker text, but never a complete marker."""

    normalization = PromptSourceNormalizationService().normalize_for_typed_deletion(
        text,
        position=position,
    )

    assert normalization.text == expected


def test_extra_closing_bracket_does_not_renormalize_completed_separator() -> None:
    """Typing after a complete marker must preserve the authored `[SEP]]` text."""

    text = "[SEP]]"

    normalization = PromptSourceNormalizationService().normalize_for_typed_edit_range(
        text,
        start=len(text) - 1,
        end=len(text),
        replacement_text="]",
    )

    assert normalization.text == text


@pytest.mark.parametrize(
    ("text", "start", "end", "expected", "caret"),
    (
        (
            "global\n[SEP]\nmiddle[SEP]\nregional",
            len("global\n[SEP]\n"),
            len("global\n[SEP]\nmiddle"),
            "global\n[SEP]\nmiddle\n[SEP]\nregional",
            len("global\n[SEP]\nmiddle"),
        ),
        (
            "global\r\n[SEP]\r\nmiddle[SEP]\r\nregional",
            len("global\r\n[SEP]\r\n"),
            len("global\r\n[SEP]\r\nmiddle"),
            "global\r\n[SEP]\r\nmiddle\r\n[SEP]\r\nregional",
            len("global\r\n[SEP]\r\nmiddle"),
        ),
    ),
)
def test_adjacent_separator_partition_insertion_preserves_both_markers(
    text: str,
    start: int,
    end: int,
    expected: str,
    caret: int,
) -> None:
    """Typed content should populate a zero-length partition on its own line."""

    normalization = PromptSourceNormalizationService().normalize_for_typed_edit_range(
        text,
        start=start,
        end=end,
        replacement_text=text[start:end],
    )

    assert normalization.text == expected
    assert normalization.boundary_positions[end] == caret


def test_paste_into_adjacent_separator_partition_preserves_both_markers() -> None:
    """Pasted content should populate the same zero-length regional partition."""

    text = "global\n[SEP]\npasted content[SEP]\nregional"
    start = len("global\n[SEP]\n")
    end = start + len("pasted content")

    normalization = PromptSourceNormalizationService().normalize_for_paste_range(
        text,
        start=start,
        end=end,
    )

    assert normalization.text == ("global\n[SEP]\npasted content\n[SEP]\nregional")
    assert normalization.boundary_positions[end] == end


def test_ordinary_insertion_before_separator_is_not_rewritten() -> None:
    """Only a zero-length partition between adjacent marker lines gains a newline."""

    text = "global\ncontentmiddle[SEP]\nregional"
    start = len("global\ncontent")
    end = start + len("middle")

    normalization = PromptSourceNormalizationService().normalize_for_typed_edit_range(
        text,
        start=start,
        end=end,
        replacement_text="middle",
    )

    assert normalization.text == text
