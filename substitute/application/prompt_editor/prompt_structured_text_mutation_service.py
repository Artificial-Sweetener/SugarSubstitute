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

"""Prepare structure-preserving text replacements for decoded prompt values."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt import SourceRange

from .prompt_document_semantics import PromptDocumentSemantics


@dataclass(frozen=True, slots=True)
class PromptStructuredTextReplacement:
    """Describe a raw replacement prepared from one logical prompt edit."""

    source_range: SourceRange
    replacement_text: str
    exact_source: bool
    cursor_position: int


class PromptStructuredTextMutationService:
    """Translate prompt-value edits into structure-safe raw replacements."""

    def __init__(self, document_semantics: PromptDocumentSemantics) -> None:
        """Store the authoritative value-mapping and replacement owner."""

        self._document_semantics = document_semantics

    @property
    def uses_structured_prompt_values(self) -> bool:
        """Return whether edits require structured value translation."""

        return self._document_semantics.uses_structured_prompt_values

    def replacement_for_range(
        self,
        source_text: str,
        source_range: SourceRange,
        replacement_text: str,
    ) -> PromptStructuredTextReplacement | None:
        """Prepare one replacement that cannot cross prompt-value boundaries."""

        if not self._document_semantics.uses_structured_prompt_values:
            return PromptStructuredTextReplacement(
                source_range=source_range,
                replacement_text=replacement_text,
                exact_source=False,
                cursor_position=source_range.start + len(replacement_text),
            )
        mappings = tuple(
            mapping
            for mapping in self._document_semantics.value_mappings_for_text(source_text)
            if mapping.source_range.start <= source_range.start
            and source_range.end <= mapping.source_range.end
        )
        if len(mappings) != 1:
            return None
        mapping = mappings[0]
        try:
            logical_range = mapping.logical_range_for_source_range(source_range)
        except ValueError:
            return None
        updated_logical_text = (
            mapping.logical_text[: logical_range.start]
            + replacement_text
            + mapping.logical_text[logical_range.end :]
        )
        logical_cursor_position = logical_range.start + len(replacement_text)
        updated_source, cursor_position = (
            self._document_semantics.replace_value_text_with_cursor(
                source_text,
                mapping.value_id,
                updated_logical_text,
                logical_cursor_position,
            )
        )
        return PromptStructuredTextReplacement(
            source_range=SourceRange(0, len(source_text)),
            replacement_text=updated_source,
            exact_source=True,
            cursor_position=cursor_position,
        )

    def delimited_insertion_for_position(
        self,
        source_text: str,
        source_position: int,
        insertion_text: str,
    ) -> PromptStructuredTextReplacement | None:
        """Insert comma-delimited text at a value-local segment boundary."""

        if not self.uses_structured_prompt_values:
            return None
        mapping = self._document_semantics.value_mapping_at_position(
            source_text,
            source_position,
        )
        if mapping is None:
            return None
        try:
            logical_position = mapping.logical_range_for_source_range(
                SourceRange(source_position, source_position)
            ).start
        except ValueError:
            return None
        insertion_position = _logical_segment_end(
            mapping.logical_text,
            logical_position,
        )
        delimited_text = _delimited_text(
            source_text=mapping.logical_text,
            insertion_position=insertion_position,
            insertion_text=insertion_text.strip(),
        )
        source_insertion_range = mapping.source_range_for_logical_range(
            SourceRange(insertion_position, insertion_position)
        )
        return self.replacement_for_range(
            source_text,
            source_insertion_range,
            delimited_text,
        )


def _logical_segment_end(text: str, position: int) -> int:
    """Return the next comma or newline boundary inside one prompt value."""

    for index in range(position, len(text)):
        if text[index] in {",", "\n"}:
            return index
    return len(text)


def _delimited_text(
    *,
    source_text: str,
    insertion_position: int,
    insertion_text: str,
) -> str:
    """Add only separators needed at one prompt segment boundary."""

    left_trimmed = source_text[:insertion_position].rstrip()
    right_text = source_text[insertion_position:]
    prefix = ""
    suffix = ""
    if left_trimmed:
        prefix = " " if left_trimmed.endswith(",") else ", "
    if right_text and not right_text.startswith((",", "\n")):
        suffix = ", "
    return f"{prefix}{insertion_text}{suffix}"


__all__ = [
    "PromptStructuredTextMutationService",
    "PromptStructuredTextReplacement",
]
