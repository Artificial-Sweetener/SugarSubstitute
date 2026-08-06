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

"""Build regional prompt structure during the canonical prompt scan."""

from __future__ import annotations

from substitute.domain.prompt.document.ranges import SourceRange
from substitute.domain.prompt.regions.models import (
    PromptRegionPartition,
    PromptRegionSeparator,
    PromptRegionStructure,
)
from substitute.domain.prompt.regions.syntax import (
    REGION_SEPARATOR_TOKEN,
    PromptRegionSeparatorSyntax,
    region_separator_at,
)


class PromptRegionStructureBuilder:
    """Accumulate exact standalone separators without rescanning prompt source."""

    def __init__(self) -> None:
        """Initialize an empty ordered separator collection."""

        self._separators: list[PromptRegionSeparator] = []

    def accept_separator_at(
        self, text: str, index: int
    ) -> PromptRegionSeparatorSyntax | None:
        """Record an exact whole-line separator beginning at one scan position."""

        match = region_separator_at(text, index, require_standalone=True)
        if match is None:
            return None

        line_end = match.token_end
        if line_end < len(text):
            if text.startswith("\r\n", line_end):
                line_end += 2
            else:
                line_end += 1
        self._separators.append(
            PromptRegionSeparator(
                token_range=SourceRange(index, match.token_end),
                line_range=SourceRange(index, line_end),
                name_range=(
                    SourceRange(match.name_start, match.name_end)
                    if match.name_start is not None and match.name_end is not None
                    else None
                ),
                name=match.name,
            )
        )
        return match

    def build(self, source_length: int) -> PromptRegionStructure:
        """Return immutable partitions spanning source outside separator lines."""

        partitions: list[PromptRegionPartition] = []
        partition_start = 0
        for separator in self._separators:
            partitions.append(
                PromptRegionPartition(
                    index=len(partitions),
                    source_range=SourceRange(
                        partition_start,
                        separator.line_range.start,
                    ),
                    is_global=not partitions,
                )
            )
            partition_start = separator.line_range.end
        partitions.append(
            PromptRegionPartition(
                index=len(partitions),
                source_range=SourceRange(partition_start, source_length),
                is_global=not partitions,
            )
        )
        return PromptRegionStructure(
            separators=tuple(self._separators),
            partitions=tuple(partitions),
        )


__all__ = ["PromptRegionStructureBuilder", "REGION_SEPARATOR_TOKEN"]
