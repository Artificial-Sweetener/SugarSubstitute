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

"""Define immutable application requests for prompt reorder commits."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderStateView,
)


@dataclass(frozen=True, slots=True)
class PromptReorderLayoutCommitRequest:
    """Carry one prepared reorder mutation request across the editing boundary."""

    selected_chip_index: int | None
    reorder_state: PromptReorderStateView
    layout_view: PromptReorderLayoutView | None = None
    source_revision: int | None = None
    source_length: int | None = None
    selection_start_offset_within_selected_chip: int | None = None
    selection_end_offset_within_selected_chip: int | None = None

    def __post_init__(self) -> None:
        """Reject incomplete or invalid prepared source identities."""

        if self.source_revision is None:
            if self.source_length is not None:
                raise ValueError("Source length requires a source revision.")
            return
        if self.source_revision < 0:
            raise ValueError("Source revision must be non-negative.")
        if self.source_length is not None and self.source_length < 0:
            raise ValueError("Source length must be non-negative.")

    def source_matches(
        self,
        *,
        source_revision: int,
        source_length: int,
    ) -> bool:
        """Return whether the live source still matches this prepared request."""

        if self.source_revision is None:
            return True
        if self.source_revision != source_revision:
            return False
        return self.source_length is None or self.source_length == source_length


__all__ = ["PromptReorderLayoutCommitRequest"]
