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

"""Parse CSV cells while retaining exact raw-source character ranges."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt import SourceRange


@dataclass(frozen=True, slots=True)
class WildcardCsvCell:
    """Describe one decoded CSV cell and its raw-source mapping."""

    row_index: int
    column_index: int
    source_range: SourceRange
    value: str
    value_character_ranges: tuple[SourceRange, ...]
    quoted: bool
    post_quote_text: str


@dataclass(frozen=True, slots=True)
class WildcardCsvDocument:
    """Describe a source-mapped CSV document or one fail-closed parse result."""

    records: tuple[tuple[WildcardCsvCell, ...], ...]
    valid: bool


def parse_wildcard_csv_document(source_text: str) -> WildcardCsvDocument:
    """Return CSV records with decoded character-to-source mappings."""

    records: list[tuple[WildcardCsvCell, ...]] = []
    row: list[WildcardCsvCell] = []
    row_index = 0
    column_index = 0
    index = 0
    valid = True
    while index <= len(source_text):
        cell_start = index
        value_characters: list[str] = []
        character_ranges: list[SourceRange] = []
        quoted = index < len(source_text) and source_text[index] == '"'
        closed_quote = not quoted
        post_quote_text = ""
        if quoted:
            index += 1
            while index < len(source_text):
                character = source_text[index]
                if character != '"':
                    value_characters.append(character)
                    character_ranges.append(SourceRange(index, index + 1))
                    index += 1
                    continue
                if index + 1 < len(source_text) and source_text[index + 1] == '"':
                    value_characters.append('"')
                    character_ranges.append(SourceRange(index, index + 2))
                    index += 2
                    continue
                index += 1
                closed_quote = True
                break
            if not closed_quote:
                valid = False
            post_quote_start = index
            while index < len(source_text) and source_text[index] not in ",\r\n":
                if not source_text[index].isspace():
                    valid = False
                index += 1
            post_quote_text = source_text[post_quote_start:index]
        else:
            while index < len(source_text) and source_text[index] not in ",\r\n":
                if source_text[index] == '"':
                    valid = False
                value_characters.append(source_text[index])
                character_ranges.append(SourceRange(index, index + 1))
                index += 1

        row.append(
            WildcardCsvCell(
                row_index=row_index,
                column_index=column_index,
                source_range=SourceRange(cell_start, index),
                value="".join(value_characters),
                value_character_ranges=tuple(character_ranges),
                quoted=quoted,
                post_quote_text=post_quote_text,
            )
        )
        column_index += 1
        if index >= len(source_text):
            records.append(tuple(row))
            break
        if source_text[index] == ",":
            index += 1
            continue
        if source_text[index] == "\r":
            index += 1
            if index < len(source_text) and source_text[index] == "\n":
                index += 1
        elif source_text[index] == "\n":
            index += 1
        records.append(tuple(row))
        row = []
        row_index += 1
        column_index = 0
        if index == len(source_text):
            break
    return WildcardCsvDocument(
        records=tuple(records),
        valid=valid,
    )


__all__ = [
    "WildcardCsvCell",
    "WildcardCsvDocument",
    "parse_wildcard_csv_document",
]
