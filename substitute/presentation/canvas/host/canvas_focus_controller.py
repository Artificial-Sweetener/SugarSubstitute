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

"""Coordinate generic canvas host focus without domain policy."""

from __future__ import annotations


class CanvasFocusController:
    """Focus docked canvas pages through host-owned tab and stack state."""

    @staticmethod
    def focus_attached_canvas(host: object, label: str) -> bool:
        """Select one docked canvas page and return whether focus changed."""

        floating_windows = getattr(host, "floating_windows", {})
        pivot = getattr(host, "pivot", None)
        stack = getattr(host, "stack", None)
        pivot_items = getattr(pivot, "items", {})
        if label in floating_windows:
            return False
        if label not in pivot_items:
            return False
        stack_index_for_label = getattr(host, "_stack_index_for_label", None)
        if callable(stack_index_for_label):
            stack_index = stack_index_for_label(label)
        else:
            stack_index = CanvasFocusController._stack_index_for_label(host, label)
        if stack_index < 0:
            return False
        set_current_item = getattr(pivot, "setCurrentItem", None)
        set_current_index = getattr(stack, "setCurrentIndex", None)
        if callable(set_current_item):
            set_current_item(label)
        if callable(set_current_index):
            set_current_index(stack_index)
        return True

    @staticmethod
    def _stack_index_for_label(host: object, label: str) -> int:
        """Return the current stack index for one docked wrapper."""

        stack = getattr(host, "stack", None)
        wrapper = getattr(host, "wrapper_map", {}).get(label)
        index_of = getattr(stack, "indexOf", None)
        if wrapper is not None and callable(index_of):
            return int(index_of(wrapper))
        legacy_indices = getattr(host, "tab_indices", {})
        if isinstance(legacy_indices, dict):
            return int(legacy_indices.get(label, -1))
        return -1


__all__ = ["CanvasFocusController"]
