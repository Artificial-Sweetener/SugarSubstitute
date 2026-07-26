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

"""Resolve cursor selection into immutable reorder-session selection state."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.views import PromptReorderChipView


@dataclass(frozen=True, slots=True)
class PromptReorderSelectionCapture:
    """Carry one cursor selection resolved against reorder chip boundaries."""

    active_segment_index: int | None
    selection_start: int
    selection_end: int
    selection_start_offset_within_active_chip: int | None
    selection_end_offset_within_active_chip: int | None


class PromptReorderSelectionCapturePolicy:
    """Resolve active-chip and relative-selection facts in one bounded pass."""

    def capture(
        self,
        chips: tuple[PromptReorderChipView, ...],
        *,
        cursor_position: int,
        selection_start: int,
        selection_end: int,
        selection_empty: bool,
    ) -> PromptReorderSelectionCapture:
        """Return the session selection represented by one cursor snapshot."""

        candidate_positions: tuple[int, ...]
        if selection_empty:
            candidate_positions = (cursor_position,)
            captured_start = cursor_position
            captured_end = cursor_position
        else:
            candidate_positions = (
                selection_start,
                max(selection_start, selection_end - 1),
            )
            captured_start = selection_start
            captured_end = selection_end

        active_chip = self._active_chip(chips, positions=candidate_positions)
        start_offset = None
        end_offset = None
        if (
            active_chip is not None
            and self._contains(active_chip, captured_start)
            and self._contains(active_chip, captured_end)
        ):
            start_offset = captured_start - active_chip.selection_start
            end_offset = captured_end - active_chip.selection_start
        return PromptReorderSelectionCapture(
            active_segment_index=None if active_chip is None else active_chip.index,
            selection_start=captured_start,
            selection_end=captured_end,
            selection_start_offset_within_active_chip=start_offset,
            selection_end_offset_within_active_chip=end_offset,
        )

    def _active_chip(
        self,
        chips: tuple[PromptReorderChipView, ...],
        *,
        positions: tuple[int, ...],
    ) -> PromptReorderChipView | None:
        """Return a containing chip or the nearest chip preceding a boundary."""

        primary_position = positions[0]
        secondary_position = positions[1] if len(positions) > 1 else None
        primary_containing: PromptReorderChipView | None = None
        secondary_containing: PromptReorderChipView | None = None
        primary_preceding: PromptReorderChipView | None = None
        secondary_preceding: PromptReorderChipView | None = None
        for chip in chips:
            if primary_containing is None and self._contains(chip, primary_position):
                primary_containing = chip
            if chip.selection_end <= primary_position and (
                primary_preceding is None
                or chip.selection_end > primary_preceding.selection_end
            ):
                primary_preceding = chip
            if secondary_position is None:
                continue
            if secondary_containing is None and self._contains(
                chip, secondary_position
            ):
                secondary_containing = chip
            if chip.selection_end <= secondary_position and (
                secondary_preceding is None
                or chip.selection_end > secondary_preceding.selection_end
            ):
                secondary_preceding = chip
        return (
            primary_containing
            or secondary_containing
            or primary_preceding
            or secondary_preceding
        )

    @staticmethod
    def _contains(chip: PromptReorderChipView, position: int) -> bool:
        """Return whether one cursor boundary belongs to a chip selection range."""

        return chip.selection_start <= position <= chip.selection_end


__all__ = [
    "PromptReorderSelectionCapture",
    "PromptReorderSelectionCapturePolicy",
]
