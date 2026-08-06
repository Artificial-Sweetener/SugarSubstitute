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

"""Define immutable regional partition structure for prompt documents."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.domain.prompt.document.ranges import SourceRange


@dataclass(frozen=True, slots=True)
class PromptRegionSeparator:
    """Represent one exact standalone regional prompt separator line."""

    token_range: SourceRange
    line_range: SourceRange
    name_range: SourceRange | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        """Require the structural line to contain the separator token."""

        if not self.line_range.encloses(self.token_range):
            raise ValueError("Separator line range must enclose its token range.")
        if (self.name_range is None) != (self.name is None):
            raise ValueError("Separator name and name range must be present together.")
        if self.name_range is not None and not self.token_range.encloses(
            self.name_range
        ):
            raise ValueError("Separator token range must enclose its name range.")


@dataclass(frozen=True, slots=True)
class PromptRegionPartition:
    """Represent one global or regional source partition between separators."""

    index: int
    source_range: SourceRange
    is_global: bool


@dataclass(frozen=True, slots=True)
class PromptRegionStructure:
    """Own exact separators and every global or regional source partition."""

    separators: tuple[PromptRegionSeparator, ...]
    partitions: tuple[PromptRegionPartition, ...]

    def __post_init__(self) -> None:
        """Require one global partition and one additional partition per separator."""

        if len(self.partitions) != len(self.separators) + 1:
            raise ValueError(
                "Region structure must contain one more partition than separator."
            )
        if not self.partitions or not self.partitions[0].is_global:
            raise ValueError("Region structure must begin with a global partition.")
        if any(partition.is_global for partition in self.partitions[1:]):
            raise ValueError("Only the first region partition may be global.")


__all__ = [
    "PromptRegionPartition",
    "PromptRegionSeparator",
    "PromptRegionStructure",
]
