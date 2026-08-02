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

"""Project authoritative canvas-host state into the docked widget stack."""

from __future__ import annotations

from PySide6.QtWidgets import QStackedLayout, QVBoxLayout, QWidget

from substitute.presentation.canvas.host.canvas_host_state import (
    CanvasHostEntry,
    CanvasHostPage,
    CanvasHostState,
)


def create_canvas_host_entry(page: CanvasHostPage) -> CanvasHostEntry:
    """Create the single runtime entry and wrapper for a configured page."""

    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(page.widget)
    return CanvasHostEntry(
        page=page,
        wrapper=wrapper,
        available=page.default_available,
    )


class CanvasHostStack:
    """Keep a stacked layout synchronized with selectable state entries."""

    def __init__(self) -> None:
        """Create an initially empty docked canvas stack."""

        self.layout = QStackedLayout()

    def synchronize(self, state: CanvasHostState) -> None:
        """Apply membership, durable order, and active selection from state."""

        selectable_entries = state.selectable_entries()
        selectable_wrappers = {entry.wrapper for entry in selectable_entries}
        for index in reversed(range(self.layout.count())):
            widget = self.layout.widget(index)
            if widget is not None and widget not in selectable_wrappers:
                self.layout.removeWidget(widget)

        for target_index, entry in enumerate(selectable_entries):
            current_index = self.layout.indexOf(entry.wrapper)
            if current_index == target_index:
                continue
            if current_index >= 0:
                self.layout.removeWidget(entry.wrapper)
            self.layout.insertWidget(target_index, entry.wrapper)

        active_route_key = state.active_route_key
        if active_route_key is None:
            return
        active_entry = state.entry(active_route_key)
        if active_entry is None:
            return
        active_index = self.layout.indexOf(active_entry.wrapper)
        if active_index >= 0:
            self.layout.setCurrentIndex(active_index)

    def contains(self, entry: CanvasHostEntry) -> bool:
        """Return whether an entry's wrapper currently belongs to the stack."""

        return self.layout.indexOf(entry.wrapper) >= 0


__all__ = ["CanvasHostStack", "create_canvas_host_entry"]
