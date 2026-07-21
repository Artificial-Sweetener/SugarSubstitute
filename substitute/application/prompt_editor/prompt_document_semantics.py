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

"""Define prompt-document capabilities and structured value mappings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import overload
from typing import Hashable, Protocol

from substitute.domain.prompt import SourceRange


@dataclass(frozen=True, slots=True)
class PromptIdentityCharacterRangeSequence(Sequence[SourceRange]):
    """Expose contiguous identity character ranges without per-character objects."""

    source_start: int
    length: int

    def __post_init__(self) -> None:
        """Reject negative coordinate identities."""

        if self.source_start < 0 or self.length < 0:
            raise ValueError(
                "Identity character range coordinates must be non-negative."
            )

    def __len__(self) -> int:
        """Return the logical character count."""

        return self.length

    @overload
    def __getitem__(self, index: int) -> SourceRange: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[SourceRange, ...]: ...

    def __getitem__(self, index: int | slice) -> SourceRange | tuple[SourceRange, ...]:
        """Return one lazily materialized range or a bounded concrete slice."""

        if isinstance(index, slice):
            start, stop, step = index.indices(self.length)
            return tuple(self[position] for position in range(start, stop, step))
        normalized_index = index + self.length if index < 0 else index
        if normalized_index < 0 or normalized_index >= self.length:
            raise IndexError(index)
        source_position = self.source_start + normalized_index
        return SourceRange(source_position, source_position + 1)

    def contains_only_ranges_within(self, source_range: SourceRange) -> bool:
        """Validate the full identity sequence in constant time."""

        return (
            self.source_start >= source_range.start
            and self.source_start + self.length <= source_range.end
        )

    def logical_range_for_source_range(
        self,
        source_range: SourceRange,
    ) -> SourceRange | None:
        """Translate an exact identity-mapped source range in constant time."""

        if (
            source_range.start < self.source_start
            or source_range.end > self.source_start + self.length
        ):
            return None
        return SourceRange(
            source_range.start - self.source_start,
            source_range.end - self.source_start,
        )


@dataclass(frozen=True, slots=True)
class PromptValueMapping:
    """Map one logical prompt value to its structured source coordinates."""

    value_id: str
    source_range: SourceRange
    logical_text: str
    logical_character_ranges: Sequence[SourceRange]

    def __post_init__(self) -> None:
        """Reject value mappings that cannot translate logical ranges safely."""

        if not self.value_id:
            raise ValueError("Prompt value mapping id must not be empty.")
        if len(self.logical_character_ranges) != len(self.logical_text):
            raise ValueError(
                "Prompt value character ranges must align with logical text."
            )
        ranges_are_valid = (
            self.logical_character_ranges.contains_only_ranges_within(self.source_range)
            if isinstance(
                self.logical_character_ranges,
                PromptIdentityCharacterRangeSequence,
            )
            else not any(
                character_range.start < self.source_range.start
                or character_range.end > self.source_range.end
                for character_range in self.logical_character_ranges
            )
        )
        if not ranges_are_valid:
            raise ValueError(
                "Prompt value character mappings must remain inside the value range."
            )

    def source_range_for_logical_range(self, logical_range: SourceRange) -> SourceRange:
        """Translate one logical half-open range into its raw source extent."""

        if logical_range.start < 0 or logical_range.end > len(self.logical_text):
            raise ValueError("Logical prompt range lies outside its value mapping.")
        if logical_range.start == logical_range.end:
            if logical_range.start == len(self.logical_character_ranges):
                return SourceRange(self.source_range.end, self.source_range.end)
            position = self.logical_character_ranges[logical_range.start].start
            return SourceRange(position, position)
        first = self.logical_character_ranges[logical_range.start]
        last = self.logical_character_ranges[logical_range.end - 1]
        return SourceRange(first.start, last.end)

    def logical_range_for_source_range(self, source_range: SourceRange) -> SourceRange:
        """Translate one exact mapped raw range into logical coordinates."""

        if (
            source_range.start < self.source_range.start
            or source_range.end > self.source_range.end
        ):
            raise ValueError("Source range lies outside its value mapping.")
        if isinstance(
            self.logical_character_ranges,
            PromptIdentityCharacterRangeSequence,
        ):
            logical_range = (
                self.logical_character_ranges.logical_range_for_source_range(
                    source_range
                )
            )
            if logical_range is not None:
                return logical_range
        if source_range.start == source_range.end:
            for index, character_range in enumerate(self.logical_character_ranges):
                if source_range.start == character_range.start:
                    return SourceRange(index, index)
            if source_range.start == self.source_range.end:
                position = len(self.logical_character_ranges)
                return SourceRange(position, position)
            raise ValueError("Source position does not align with a logical character.")
        logical_start = next(
            (
                index
                for index, character_range in enumerate(self.logical_character_ranges)
                if character_range.start == source_range.start
            ),
            None,
        )
        logical_end = next(
            (
                index + 1
                for index, character_range in enumerate(self.logical_character_ranges)
                if character_range.end == source_range.end
            ),
            None,
        )
        if logical_start is None or logical_end is None or logical_start > logical_end:
            raise ValueError("Source range does not align with logical characters.")
        return SourceRange(logical_start, logical_end)


class PromptDocumentSemantics(Protocol):
    """Own capabilities and value translation for one source-document kind."""

    @property
    def identity(self) -> Hashable:
        """Return a stable cache identity for these document semantics."""

    @property
    def scenes_enabled(self) -> bool:
        """Return whether scene syntax has behavioral meaning in this document."""

    @property
    def uses_structured_prompt_values(self) -> bool:
        """Return whether prompt values require source decoding and re-encoding."""

    @property
    def isolates_duplicate_diagnostics_by_value(self) -> bool:
        """Return whether duplicate tags are evaluated per wildcard value."""

    def prompt_content_text(self, source_text: str) -> str:
        """Return document-wide prompt content without storage structure."""

    def value_mappings_for_text(
        self,
        source_text: str,
    ) -> tuple[PromptValueMapping, ...]:
        """Return source-mapped prompt values in document order."""

    def value_mapping_at_position(
        self,
        source_text: str,
        source_position: int,
    ) -> PromptValueMapping | None:
        """Return the prompt value containing one source position."""

    def unsupported_scene_marker_ranges(
        self,
        source_text: str,
    ) -> tuple[SourceRange, ...]:
        """Return unsafe leading scene-marker ranges for this document."""

    def replace_value_text(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
    ) -> str:
        """Replace one logical prompt value while preserving document structure."""

    def replace_value_text_with_cursor(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
        logical_cursor_position: int,
    ) -> tuple[str, int]:
        """Replace one prompt value and map its logical caret to raw source."""


class OrdinaryPromptDocumentSemantics:
    """Treat an ordinary prompt as one scene-capable source document."""

    @property
    def identity(self) -> Hashable:
        """Return the stable ordinary-prompt semantics identity."""

        return "ordinary-prompt-v1"

    @property
    def scenes_enabled(self) -> bool:
        """Keep existing scene behavior active for ordinary prompts."""

        return True

    @property
    def uses_structured_prompt_values(self) -> bool:
        """Use ordinary source coordinates without a structure codec."""

        return False

    @property
    def isolates_duplicate_diagnostics_by_value(self) -> bool:
        """Preserve ordinary scene-aware duplicate behavior."""

        return False

    def prompt_content_text(self, source_text: str) -> str:
        """Return the complete ordinary prompt source as prompt content."""

        return source_text

    def value_mappings_for_text(
        self,
        source_text: str,
    ) -> tuple[PromptValueMapping, ...]:
        """Return one source mapping for the complete ordinary prompt."""

        return (
            PromptValueMapping(
                value_id="prompt",
                source_range=SourceRange(0, len(source_text)),
                logical_text=source_text,
                logical_character_ranges=PromptIdentityCharacterRangeSequence(
                    source_start=0,
                    length=len(source_text),
                ),
            ),
        )

    def value_mapping_at_position(
        self,
        source_text: str,
        source_position: int,
    ) -> PromptValueMapping | None:
        """Return the ordinary prompt mapping for every valid caret position."""

        if not 0 <= source_position <= len(source_text):
            return None
        return self.value_mappings_for_text(source_text)[0]

    def unsupported_scene_marker_ranges(
        self,
        source_text: str,
    ) -> tuple[SourceRange, ...]:
        """Return no unsupported markers because ordinary prompts support scenes."""

        del source_text
        return ()

    def replace_value_text(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
    ) -> str:
        """Replace the complete ordinary prompt value."""

        if value_id != "prompt":
            raise ValueError("Unknown ordinary prompt value.")
        del source_text
        return logical_text

    def replace_value_text_with_cursor(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
        logical_cursor_position: int,
    ) -> tuple[str, int]:
        """Replace an ordinary prompt and retain its logical caret position."""

        updated = self.replace_value_text(source_text, value_id, logical_text)
        if not 0 <= logical_cursor_position <= len(logical_text):
            raise ValueError("Ordinary prompt cursor lies outside replacement text.")
        return updated, logical_cursor_position


class PromptDocumentSemanticsController:
    """Publish replaceable document semantics through one stable editor dependency."""

    def __init__(self, semantics: PromptDocumentSemantics) -> None:
        """Store the initial authoritative document semantics."""

        self._semantics = semantics

    @property
    def identity(self) -> Hashable:
        """Return the active semantics cache identity."""

        return self._semantics.identity

    @property
    def scenes_enabled(self) -> bool:
        """Return whether active semantics support scenes."""

        return self._semantics.scenes_enabled

    @property
    def uses_structured_prompt_values(self) -> bool:
        """Return whether active source requires structure-aware translation."""

        return self._semantics.uses_structured_prompt_values

    @property
    def isolates_duplicate_diagnostics_by_value(self) -> bool:
        """Return whether active values own separate duplicate namespaces."""

        return self._semantics.isolates_duplicate_diagnostics_by_value

    def prompt_content_text(self, source_text: str) -> str:
        """Return document-wide prompt content from the active semantics."""

        return self._semantics.prompt_content_text(source_text)

    def replace(self, semantics: PromptDocumentSemantics) -> bool:
        """Replace active semantics and report whether their identity changed."""

        if semantics.identity == self._semantics.identity:
            return False
        self._semantics = semantics
        return True

    def value_mappings_for_text(
        self,
        source_text: str,
    ) -> tuple[PromptValueMapping, ...]:
        """Return prompt value mappings from the active semantics."""

        return self._semantics.value_mappings_for_text(source_text)

    def value_mapping_at_position(
        self,
        source_text: str,
        source_position: int,
    ) -> PromptValueMapping | None:
        """Return the active prompt value containing one source position."""

        return self._semantics.value_mapping_at_position(
            source_text,
            source_position,
        )

    def unsupported_scene_marker_ranges(
        self,
        source_text: str,
    ) -> tuple[SourceRange, ...]:
        """Return rejected scene markers from the active semantics."""

        return self._semantics.unsupported_scene_marker_ranges(source_text)

    def replace_value_text(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
    ) -> str:
        """Replace one value through the active semantics owner."""

        return self._semantics.replace_value_text(
            source_text,
            value_id,
            logical_text,
        )

    def replace_value_text_with_cursor(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
        logical_cursor_position: int,
    ) -> tuple[str, int]:
        """Replace one active value and map its logical caret."""

        return self._semantics.replace_value_text_with_cursor(
            source_text,
            value_id,
            logical_text,
            logical_cursor_position,
        )


def value_mapping_at_source_position(
    mappings: tuple[PromptValueMapping, ...],
    source_position: int,
) -> PromptValueMapping | None:
    """Return the value mapping containing one source or trailing caret."""

    for mapping in mappings:
        if (
            not mapping.logical_text
            and mapping.source_range.start == source_position
            and mapping.source_range.end == source_position
        ):
            return mapping
        if mapping.source_range.start <= source_position < mapping.source_range.end:
            return mapping
        if source_position == mapping.source_range.end and mapping.logical_text:
            return mapping
    return None


def leading_scene_marker_ranges(
    mappings: tuple[PromptValueMapping, ...],
) -> tuple[SourceRange, ...]:
    """Return raw ranges for leading ``**`` prefixes in logical prompt values."""

    marker_ranges: list[SourceRange] = []
    for mapping in mappings:
        leading_whitespace = len(mapping.logical_text) - len(
            mapping.logical_text.lstrip()
        )
        marker_end = leading_whitespace + 2
        if mapping.logical_text[leading_whitespace:marker_end] != "**":
            continue
        marker_ranges.append(
            mapping.source_range_for_logical_range(
                SourceRange(leading_whitespace, marker_end)
            )
        )
    return tuple(marker_ranges)


__all__ = [
    "OrdinaryPromptDocumentSemantics",
    "PromptDocumentSemantics",
    "PromptDocumentSemanticsController",
    "PromptIdentityCharacterRangeSequence",
    "PromptValueMapping",
    "leading_scene_marker_ranges",
    "value_mapping_at_source_position",
]
