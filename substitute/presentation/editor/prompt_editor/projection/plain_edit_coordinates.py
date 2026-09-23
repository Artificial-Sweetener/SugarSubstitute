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

"""Describe source and projection coordinate changes for one plain edit."""

from __future__ import annotations

from dataclasses import dataclass

from .incremental_edit_contracts import PromptProjectionIncrementalEdit


@dataclass(frozen=True, slots=True)
class PromptSourceEditCoordinates:
    """Carry source-only coordinates shared by token and run remapping."""

    start: int
    end: int
    delta: int

    @classmethod
    def from_incremental_edit(
        cls,
        edit: PromptProjectionIncrementalEdit,
    ) -> PromptSourceEditCoordinates:
        """Return compact source coordinates for one incremental edit."""

        return cls(
            start=edit.start,
            end=edit.end,
            delta=len(edit.replacement_text) - (edit.end - edit.start),
        )


@dataclass(frozen=True, slots=True)
class PromptProjectionPlainEditCoordinates:
    """Carry the coordinate deltas shared by incremental projection owners."""

    source_start: int
    source_end: int
    source_delta: int
    projection_start: int
    projection_delta: int


def remap_source_position(
    position: int,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
    move_insert_boundary: bool,
) -> int:
    """Return one position shifted across a non-overlapping source edit."""

    if edit_start == edit_end:
        if position > edit_start or (move_insert_boundary and position == edit_start):
            return position + delta
        return position
    if position >= edit_end:
        return position + delta
    if position > edit_start:
        return edit_start
    return position


def remap_optional_source_position(
    position: int | None,
    *,
    edit_start: int,
    edit_end: int,
    delta: int,
    move_insert_boundary: bool,
) -> int | None:
    """Return an optional position shifted across one source edit."""

    if position is None:
        return None
    return remap_source_position(
        position,
        edit_start=edit_start,
        edit_end=edit_end,
        delta=delta,
        move_insert_boundary=move_insert_boundary,
    )


__all__ = [
    "PromptProjectionPlainEditCoordinates",
    "PromptSourceEditCoordinates",
    "remap_optional_source_position",
    "remap_source_position",
]
