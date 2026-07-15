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

"""Adapt shared anchored row pickers for canvas hierarchy navigation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.anchored_row_picker import (
    AnchoredRowPicker,
    AnchoredRowPickerItem as CanvasNavPickerItem,
)


class CanvasNavPicker:
    """Own scene/navigation picker configuration for canvas selectors."""

    def __init__(self, parent: QWidget) -> None:
        """Create a picker controller for a canvas navigation selector."""

        self._picker = AnchoredRowPicker(parent)

    def show_for(
        self,
        anchor: QWidget,
        *,
        items: tuple[CanvasNavPickerItem, ...],
        active_key: str,
        row_width: int | None = None,
        selected_callback: Callable[[str], None],
    ) -> None:
        """Show an anchor-aligned navigation picker for scene-like rows."""

        self._picker.show_for(
            anchor,
            items=items,
            active_key=active_key,
            row_width=row_width,
            active_text_mode="anchor_center",
            inactive_text_mode="row_left",
            selected_callback=selected_callback,
        )

    def close(self) -> None:
        """Close the visible picker popup."""

        self._picker.close()

    def is_visible(self) -> bool:
        """Return whether the picker popup is currently visible."""

        return self._picker.is_visible()


__all__ = [
    "CanvasNavPicker",
    "CanvasNavPickerItem",
]
