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

"""Map TXT wildcard values and declare their document capabilities."""

from __future__ import annotations

from typing import Hashable

from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptValueMapping,
    leading_scene_marker_ranges,
    value_mapping_at_source_position,
)
from substitute.domain.prompt import SourceRange


class WildcardTextDocumentSemantics:
    """Treat every non-empty TXT wildcard line as one prompt value."""

    @property
    def identity(self) -> Hashable:
        """Return the stable TXT wildcard semantics identity."""

        return "wildcard-txt-v1"

    @property
    def scenes_enabled(self) -> bool:
        """Disable scene behavior inside wildcard candidates."""

        return False

    @property
    def uses_structured_prompt_values(self) -> bool:
        """Keep TXT values in ordinary source coordinates."""

        return False

    @property
    def isolates_duplicate_diagnostics_by_value(self) -> bool:
        """Evaluate duplicate tags independently for each TXT wildcard."""

        return True

    def prompt_content_text(self, source_text: str) -> str:
        """Return all TXT wildcard values as one ordinary prompt document."""

        return source_text

    def value_mappings_for_text(
        self,
        source_text: str,
    ) -> tuple[PromptValueMapping, ...]:
        """Return trimmed source mappings for non-empty physical lines."""

        mappings: list[PromptValueMapping] = []
        offset = 0
        for line_index, line_with_ending in enumerate(
            source_text.splitlines(keepends=True)
        ):
            line = line_with_ending.rstrip("\r\n")
            leading_width = len(line) - len(line.lstrip())
            trailing_end = len(line.rstrip())
            if leading_width < trailing_end:
                start = offset + leading_width
                end = offset + trailing_end
                mappings.append(
                    PromptValueMapping(
                        value_id=f"txt-line:{line_index}",
                        source_range=SourceRange(start, end),
                        logical_text=source_text[start:end],
                        logical_character_ranges=tuple(
                            SourceRange(index, index + 1) for index in range(start, end)
                        ),
                    )
                )
            offset += len(line_with_ending)
        if offset < len(source_text):
            line = source_text[offset:]
            leading_width = len(line) - len(line.lstrip())
            trailing_end = len(line.rstrip())
            if leading_width < trailing_end:
                start = offset + leading_width
                end = offset + trailing_end
                mappings.append(
                    PromptValueMapping(
                        value_id=f"txt-line:{len(source_text.splitlines())}",
                        source_range=SourceRange(start, end),
                        logical_text=source_text[start:end],
                        logical_character_ranges=tuple(
                            SourceRange(index, index + 1) for index in range(start, end)
                        ),
                    )
                )
        return tuple(mappings)

    def value_mapping_at_position(
        self,
        source_text: str,
        source_position: int,
    ) -> PromptValueMapping | None:
        """Return the TXT candidate containing one source position."""

        return value_mapping_at_source_position(
            self.value_mappings_for_text(source_text), source_position
        )

    def unsupported_scene_marker_ranges(
        self,
        source_text: str,
    ) -> tuple[SourceRange, ...]:
        """Return leading scene-marker ranges from independent TXT candidates."""

        return leading_scene_marker_ranges(self.value_mappings_for_text(source_text))

    def replace_value_text(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
    ) -> str:
        """Replace one trimmed line value without changing line structure."""

        mapping = next(
            (
                candidate
                for candidate in self.value_mappings_for_text(source_text)
                if candidate.value_id == value_id
            ),
            None,
        )
        if mapping is None:
            raise ValueError("Unknown TXT wildcard value.")
        return (
            source_text[: mapping.source_range.start]
            + logical_text
            + source_text[mapping.source_range.end :]
        )

    def replace_value_text_with_cursor(
        self,
        source_text: str,
        value_id: str,
        logical_text: str,
        logical_cursor_position: int,
    ) -> tuple[str, int]:
        """Replace one line value and retain its logical caret position."""

        mapping = next(
            (
                candidate
                for candidate in self.value_mappings_for_text(source_text)
                if candidate.value_id == value_id
            ),
            None,
        )
        if mapping is None:
            raise ValueError("Unknown TXT wildcard value.")
        if not 0 <= logical_cursor_position <= len(logical_text):
            raise ValueError("TXT wildcard cursor lies outside replacement text.")
        updated = self.replace_value_text(source_text, value_id, logical_text)
        return updated, mapping.source_range.start + logical_cursor_position


__all__ = ["WildcardTextDocumentSemantics"]
