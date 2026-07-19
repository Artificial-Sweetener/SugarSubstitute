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

"""Map CSV wildcard values and declare their document capabilities."""

from __future__ import annotations

from typing import Hashable

from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptValueMapping,
    leading_scene_marker_ranges,
    value_mapping_at_source_position,
)
from substitute.domain.prompt import SourceRange

from .wildcard_csv_document_parser import (
    WildcardCsvCell,
    parse_wildcard_csv_document,
)


class WildcardCsvDocumentSemantics:
    """Treat each valid CSV data cell as one source-mapped prompt value."""

    @property
    def identity(self) -> Hashable:
        """Return the stable CSV wildcard semantics identity."""

        return "wildcard-csv-v1"

    @property
    def scenes_enabled(self) -> bool:
        """Disable scene behavior inside CSV wildcard values."""

        return False

    @property
    def uses_structured_prompt_values(self) -> bool:
        """Decode CSV cells before applying prompt-aware behavior."""

        return True

    @property
    def isolates_duplicate_diagnostics_by_value(self) -> bool:
        """Evaluate duplicate tags independently for each CSV wildcard value."""

        return True

    def prompt_content_text(self, source_text: str) -> str:
        """Return all decoded CSV values as one document-wide prompt."""

        return "\n".join(
            mapping.logical_text
            for mapping in self.value_mappings_for_text(source_text)
        )

    def value_mappings_for_text(
        self,
        source_text: str,
    ) -> tuple[PromptValueMapping, ...]:
        """Return trimmed source mappings for valid CSV data cells."""

        document = parse_wildcard_csv_document(source_text)
        if not document.valid:
            return ()
        mappings: list[PromptValueMapping] = []
        for record in document.records[1:]:
            for cell in record:
                leading_width = len(cell.value) - len(cell.value.lstrip())
                trailing_end = len(cell.value.rstrip())
                character_ranges = cell.value_character_ranges[
                    leading_width:trailing_end
                ]
                if not character_ranges:
                    anchor = _cell_value_anchor(cell, leading_width)
                    mappings.append(
                        PromptValueMapping(
                            value_id=(f"csv-cell:{cell.row_index}:{cell.column_index}"),
                            source_range=SourceRange(anchor, anchor),
                            logical_text="",
                            logical_character_ranges=(),
                        )
                    )
                    continue
                mappings.append(
                    PromptValueMapping(
                        value_id=f"csv-cell:{cell.row_index}:{cell.column_index}",
                        source_range=SourceRange(
                            character_ranges[0].start,
                            character_ranges[-1].end,
                        ),
                        logical_text=cell.value[leading_width:trailing_end],
                        logical_character_ranges=character_ranges,
                    )
                )
        return tuple(mappings)

    def value_mapping_at_position(
        self,
        source_text: str,
        source_position: int,
    ) -> PromptValueMapping | None:
        """Return the CSV data cell containing one source position."""

        return value_mapping_at_source_position(
            self.value_mappings_for_text(source_text), source_position
        )

    def unsupported_scene_marker_ranges(
        self,
        source_text: str,
    ) -> tuple[SourceRange, ...]:
        """Return leading scene-marker ranges from CSV data-cell values."""

        return leading_scene_marker_ranges(self.value_mappings_for_text(source_text))

    def replace_value_text(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
    ) -> str:
        """Replace one decoded cell value while retaining valid CSV structure."""

        updated, _cursor_position = self.replace_value_text_with_cursor(
            source_text,
            value_id,
            logical_text,
            len(logical_text),
        )
        return updated

    def replace_value_text_with_cursor(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
        logical_cursor_position: int,
    ) -> tuple[str, int]:
        """Replace one decoded cell and map its logical caret into raw CSV."""

        cell = _cell_for_value(source_text, value_id)
        if not 0 <= logical_cursor_position <= len(logical_text):
            raise ValueError("CSV wildcard cursor lies outside replacement text.")
        leading_width = len(cell.value) - len(cell.value.lstrip())
        trailing_start = len(cell.value.rstrip())
        if leading_width >= trailing_start:
            leading_text = cell.value
            trailing_text = ""
        else:
            leading_text = cell.value[:leading_width]
            trailing_text = cell.value[trailing_start:]
        value = leading_text + logical_text + trailing_text
        replacement = _serialize_csv_cell_value(
            value,
            preserve_quotes=cell.quoted,
            post_quote_text=cell.post_quote_text,
        )
        updated = (
            source_text[: cell.source_range.start]
            + replacement
            + source_text[cell.source_range.end :]
        )
        decoded_cursor_position = len(leading_text) + logical_cursor_position
        encoded_prefix = value[:decoded_cursor_position]
        raw_cursor_offset = (
            1 + len(encoded_prefix.replace('"', '""'))
            if cell.quoted or _csv_value_requires_quotes(value)
            else len(encoded_prefix)
        )
        return updated, cell.source_range.start + raw_cursor_offset


def _cell_value_anchor(cell: WildcardCsvCell, decoded_position: int) -> int:
    """Return the raw insertion anchor for one empty decoded cell value."""

    if decoded_position < len(cell.value_character_ranges):
        return cell.value_character_ranges[decoded_position].start
    if cell.value_character_ranges:
        return cell.value_character_ranges[-1].end
    return cell.source_range.start + (1 if cell.quoted else 0)


def _cell_for_value(source_text: str, value_id: str) -> WildcardCsvCell:
    """Return the parsed data cell identified by one mapped value id."""

    document = parse_wildcard_csv_document(source_text)
    if not document.valid:
        raise ValueError("Cannot mutate malformed wildcard CSV source.")
    cell = next(
        (
            candidate
            for record in document.records[1:]
            for candidate in record
            if f"csv-cell:{candidate.row_index}:{candidate.column_index}" == value_id
        ),
        None,
    )
    if cell is None:
        raise ValueError("Unknown CSV wildcard value.")
    return cell


def _serialize_csv_cell_value(
    value: str,
    *,
    preserve_quotes: bool,
    post_quote_text: str,
) -> str:
    """Serialize one CSV value while preserving existing quote ownership."""

    requires_quotes = _csv_value_requires_quotes(value)
    if preserve_quotes or requires_quotes:
        escaped_value = value.replace('"', '""')
        return f'"{escaped_value}"{post_quote_text}'
    return value


def _csv_value_requires_quotes(value: str) -> bool:
    """Return whether one value needs CSV quoting."""

    return any(character in value for character in ',"\r\n')


__all__ = ["WildcardCsvDocumentSemantics"]
