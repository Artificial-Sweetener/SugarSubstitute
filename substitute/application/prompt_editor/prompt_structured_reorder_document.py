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

"""Map decoded structured values to the ordinary prompt reorder model."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt import SourceRange

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_semantics import PromptDocumentSemantics, PromptValueMapping
from .prompt_document_views import PromptDocumentView, PromptReorderChipView
from .prompt_reorder_views import (
    PromptReorderPreviewSnapshot,
    PromptReorderSessionView,
)

_VALUE_BOUNDARY = "\r\n"


@dataclass(frozen=True, slots=True)
class _StructuredReorderValue:
    """Describe one decoded value inside the virtual reorder document."""

    mapping: PromptValueMapping
    virtual_range: SourceRange
    normalized_character_ranges: tuple[SourceRange, ...]

    def raw_range_for_virtual_range(
        self,
        source_range: SourceRange,
    ) -> SourceRange:
        """Map one value-local virtual range into raw structured source."""

        local_range = SourceRange(
            source_range.start - self.virtual_range.start,
            source_range.end - self.virtual_range.start,
        )
        logical_range = self._logical_range(local_range)
        return self.mapping.source_range_for_logical_range(logical_range)

    def _logical_range(self, normalized_range: SourceRange) -> SourceRange:
        """Map normalized newline coordinates into decoded value coordinates."""

        if normalized_range.start == normalized_range.end:
            position = normalized_range.start
            if position == len(self.normalized_character_ranges):
                logical_position = len(self.mapping.logical_text)
            else:
                logical_position = self.normalized_character_ranges[position].start
            return SourceRange(logical_position, logical_position)
        first = self.normalized_character_ranges[normalized_range.start]
        last = self.normalized_character_ranges[normalized_range.end - 1]
        return SourceRange(first.start, last.end)


@dataclass(frozen=True, slots=True)
class PromptStructuredReorderDocument:
    """Own one virtual ordinary prompt and its structured-source translation."""

    source_text: str
    virtual_text: str
    values: tuple[_StructuredReorderValue, ...]
    document_view: PromptDocumentView
    document_semantics: PromptDocumentSemantics
    document_projector: PromptDocumentProjector

    @classmethod
    def build(
        cls,
        *,
        source_text: str,
        document_semantics: PromptDocumentSemantics,
        document_projector: PromptDocumentProjector,
        value_ids: tuple[str, ...] | None = None,
    ) -> PromptStructuredReorderDocument:
        """Build a virtual prompt from decoded values in stable source order."""

        mappings = document_semantics.value_mappings_for_text(source_text)
        if value_ids is None:
            selected_mappings = tuple(
                mapping for mapping in mappings if mapping.logical_text
            )
        else:
            mappings_by_id = {mapping.value_id: mapping for mapping in mappings}
            try:
                selected_mappings = tuple(
                    mappings_by_id[value_id] for value_id in value_ids
                )
            except KeyError as error:
                raise ValueError(
                    "Structured reorder value disappeared during source translation."
                ) from error

        virtual_parts: list[str] = []
        values: list[_StructuredReorderValue] = []
        virtual_position = 0
        for index, mapping in enumerate(selected_mappings):
            if index:
                virtual_parts.append(_VALUE_BOUNDARY)
                virtual_position += len(_VALUE_BOUNDARY)
            normalized_text, character_ranges = _normalize_value_newlines(
                mapping.logical_text
            )
            value_start = virtual_position
            virtual_parts.append(normalized_text)
            virtual_position += len(normalized_text)
            values.append(
                _StructuredReorderValue(
                    mapping=mapping,
                    virtual_range=SourceRange(value_start, virtual_position),
                    normalized_character_ranges=character_ranges,
                )
            )

        virtual_text = "".join(virtual_parts)
        return cls(
            source_text=source_text,
            virtual_text=virtual_text,
            values=tuple(values),
            document_view=document_projector.build_document_view(virtual_text),
            document_semantics=document_semantics,
            document_projector=document_projector,
        )

    @property
    def value_ids(self) -> tuple[str, ...]:
        """Return structured value identities represented by this reorder model."""

        return tuple(value.mapping.value_id for value in self.values)

    def map_session(
        self,
        session: PromptReorderSessionView,
    ) -> PromptReorderSessionView:
        """Map virtual reorder chip ranges back into raw source coordinates."""

        return PromptReorderSessionView(
            chips=tuple(self.map_chip(chip) for chip in session.chips),
            reorder_state=session.reorder_state,
            layout_view=session.layout_view,
        )

    def map_chip(self, chip: PromptReorderChipView) -> PromptReorderChipView:
        """Map one virtual reorder chip into raw structured source coordinates."""

        display_range = self.raw_range_for_virtual_range(
            SourceRange(chip.display_source_start, chip.display_source_end)
        )
        selection_range = self.raw_range_for_virtual_range(
            SourceRange(chip.selection_start, chip.selection_end)
        )
        return PromptReorderChipView(
            index=chip.index,
            text=chip.text,
            serialized_text=chip.serialized_text,
            display_text=chip.display_text,
            display_source_start=display_range.start,
            display_source_end=display_range.end,
            selection_start=selection_range.start,
            selection_end=selection_range.end,
            separator_text_after=chip.separator_text_after,
            has_separator_after=chip.has_separator_after,
        )

    def source_for_virtual_text(self, virtual_text: str) -> str:
        """Encode reordered virtual values into their original source containers."""

        if not self.values:
            if virtual_text:
                raise ValueError("Structured reorder has no writable prompt values.")
            return self.source_text
        logical_values = virtual_text.split(_VALUE_BOUNDARY)
        if len(logical_values) != len(self.values):
            raise ValueError(
                "Structured reorder changed the number of prompt value containers."
            )
        updated_source = self.source_text
        for value, logical_text in zip(self.values, logical_values, strict=True):
            updated_source = self.document_semantics.replace_value_text(
                updated_source,
                value.mapping.value_id,
                logical_text,
            )
        return updated_source

    def map_preview(
        self,
        preview: PromptReorderPreviewSnapshot,
    ) -> PromptReorderPreviewSnapshot:
        """Encode one virtual preview and map all geometry ranges to raw source."""

        updated_source = self.source_for_virtual_text(preview.text)
        updated_document = PromptStructuredReorderDocument.build(
            source_text=updated_source,
            document_semantics=self.document_semantics,
            document_projector=self.document_projector,
            value_ids=self.value_ids,
        )
        if updated_document.virtual_text != preview.text:
            raise ValueError("Structured reorder preview failed round-trip validation.")
        return PromptReorderPreviewSnapshot(
            text=updated_source,
            chip_ranges_by_index={
                index: updated_document._raw_range_tuple(source_range)
                for index, source_range in preview.chip_ranges_by_index.items()
            },
            chip_rendered_ranges_by_index={
                index: updated_document._raw_range_tuple(source_range)
                for index, source_range in preview.chip_rendered_ranges_by_index.items()
            },
            chip_owned_ranges_by_index={
                index: tuple(
                    updated_document._raw_range_tuple(source_range)
                    for source_range in source_ranges
                )
                for index, source_ranges in preview.chip_owned_ranges_by_index.items()
            },
            gap_ranges_by_index={
                index: updated_document._raw_range_tuple(source_range)
                for index, source_range in preview.gap_ranges_by_index.items()
            },
        )

    def raw_range_for_virtual_range(self, source_range: SourceRange) -> SourceRange:
        """Map one virtual range into the smallest enclosing raw source range."""

        if not 0 <= source_range.start <= source_range.end <= len(self.virtual_text):
            raise ValueError("Virtual reorder range lies outside its document.")
        containing_value = next(
            (
                value
                for value in self.values
                if value.virtual_range.start <= source_range.start
                and source_range.end <= value.virtual_range.end
            ),
            None,
        )
        if containing_value is not None:
            return containing_value.raw_range_for_virtual_range(source_range)
        return SourceRange(
            self._raw_position(source_range.start, prefer_next=False),
            self._raw_position(source_range.end, prefer_next=True),
        )

    def _raw_position(self, virtual_position: int, *, prefer_next: bool) -> int:
        """Map one virtual boundary position into raw structured source."""

        for value in self.values:
            if value.virtual_range.start <= virtual_position <= value.virtual_range.end:
                return value.raw_range_for_virtual_range(
                    SourceRange(virtual_position, virtual_position)
                ).start
        previous = tuple(
            value for value in self.values if value.virtual_range.end < virtual_position
        )
        following = tuple(
            value
            for value in self.values
            if value.virtual_range.start > virtual_position
        )
        if prefer_next and following:
            return following[0].mapping.source_range.start
        if previous:
            return previous[-1].mapping.source_range.end
        if following:
            return following[0].mapping.source_range.start
        return 0

    def _raw_range_tuple(self, source_range: tuple[int, int]) -> tuple[int, int]:
        """Map one tuple range from a preview snapshot into raw coordinates."""

        raw_range = self.raw_range_for_virtual_range(SourceRange(*source_range))
        return raw_range.start, raw_range.end


def _normalize_value_newlines(text: str) -> tuple[str, tuple[SourceRange, ...]]:
    """Normalize value line breaks while retaining decoded-character mappings."""

    characters: list[str] = []
    character_ranges: list[SourceRange] = []
    index = 0
    while index < len(text):
        if text[index] == "\r":
            end = index + 1
            if end < len(text) and text[end] == "\n":
                end += 1
            characters.append("\n")
            character_ranges.append(SourceRange(index, end))
            index = end
            continue
        characters.append(text[index])
        character_ranges.append(SourceRange(index, index + 1))
        index += 1
    return "".join(characters), tuple(character_ranges)


__all__ = ["PromptStructuredReorderDocument"]
