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

"""Adapt shared anchored row pickers for output canvas batch sets."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.anchored_row_picker import (
    AnchoredRowPicker,
    AnchoredRowPickerItem,
)


class OutputSetPicker:
    """Own integer set picker adaptation for output canvas batches."""

    def __init__(self, parent: QWidget) -> None:
        """Create a picker controller for an output canvas."""

        self._picker = AnchoredRowPicker(parent)

    def show_for(
        self,
        anchor: QWidget,
        *,
        set_count: int,
        active_set_index: int,
        include_grid: bool = False,
        selected_callback: Callable[[int], None],
    ) -> None:
        """Show an anchor-aligned picker for output set indexes."""

        row_indexes = self._build_row_indexes(
            set_count=max(0, set_count),
            include_grid=include_grid,
        )
        items = tuple(
            AnchoredRowPickerItem(str(set_index), str(set_index))
            for set_index in row_indexes
        )

        def emit_integer_key(key: str) -> None:
            """Convert shared string row keys back to output set indexes."""

            selected_callback(int(key))

        self._picker.show_for(
            anchor,
            items=items,
            active_key=str(active_set_index),
            active_text_mode="row_center",
            inactive_text_mode="row_center",
            selected_callback=emit_integer_key,
        )

    def close(self) -> None:
        """Close the visible set picker popup."""

        self._picker.close()

    def is_visible(self) -> bool:
        """Return whether the picker popup is currently visible."""

        return self._picker.is_visible()

    @staticmethod
    def _build_row_indexes(
        *,
        set_count: int,
        include_grid: bool,
    ) -> tuple[int, ...]:
        """Return picker row indexes in display order."""

        if include_grid:
            return (0, *range(1, set_count + 1))
        return tuple(range(set_count, 0, -1))


__all__ = [
    "OutputSetPicker",
]
