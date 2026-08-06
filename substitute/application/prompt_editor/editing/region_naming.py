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

"""Prepare exact source replacements for authored regional prompt names."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.views import (
    PromptRegionSeparatorView,
)
from substitute.domain.prompt.regions.syntax import REGION_SEPARATOR_TOKEN


@dataclass(frozen=True, slots=True)
class PromptRegionNameReplacement:
    """Describe one source-backed regional name replacement."""

    source_start: int
    source_end: int
    replacement_text: str


class PromptRegionNamingService:
    """Validate authored names and preserve canonical separator syntax."""

    def replacement_for(
        self,
        separator: PromptRegionSeparatorView,
        authored_name: str,
    ) -> PromptRegionNameReplacement:
        """Return the smallest exact source edit for one authored name."""

        if any(character in authored_name for character in "]\r\n"):
            raise ValueError("Region names cannot contain ']' or a line break.")
        if authored_name == "":
            return PromptRegionNameReplacement(
                source_start=separator.token_start,
                source_end=separator.token_end,
                replacement_text=REGION_SEPARATOR_TOKEN,
            )
        if separator.name_start is not None and separator.name_end is not None:
            return PromptRegionNameReplacement(
                source_start=separator.name_start,
                source_end=separator.name_end,
                replacement_text=authored_name,
            )
        return PromptRegionNameReplacement(
            source_start=separator.token_start,
            source_end=separator.token_end,
            replacement_text=f"[SEP|{authored_name}]",
        )


__all__ = ["PromptRegionNameReplacement", "PromptRegionNamingService"]
