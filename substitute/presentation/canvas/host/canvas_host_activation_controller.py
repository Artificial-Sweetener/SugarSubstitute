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

"""Own attached canvas selection and optional keyboard-focus transfer."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.host.canvas_host_state import CanvasHostState


class CanvasHostActivationController:
    """Apply one explicit activation contract to authoritative host state."""

    def __init__(
        self,
        *,
        state: CanvasHostState,
        synchronize_presentation: Callable[[], None],
        canvas_activated: Callable[[str], None],
    ) -> None:
        """Store the host state and projections affected by activation."""

        self._state = state
        self._synchronize_presentation = synchronize_presentation
        self._canvas_activated = canvas_activated

    def activate(self, route_key: str, *, keyboard_focus: bool) -> bool:
        """Select an attached canvas and optionally transfer keyboard focus."""

        entry = self._state.entry(route_key)
        if entry is None or not entry.selectable:
            return False
        self._state.select(route_key)
        self._synchronize_presentation()
        self._canvas_activated(route_key)
        if keyboard_focus:
            QTimer.singleShot(
                0,
                lambda: self._settle_selected_canvas_focus(
                    route_key,
                    entry.page.widget,
                ),
            )
        return True

    def _settle_selected_canvas_focus(self, route_key: str, widget: QWidget) -> None:
        """Focus now and settle behind projections spawned by activation."""

        self._focus_selected_canvas(route_key, widget)
        QTimer.singleShot(
            0,
            lambda: self._focus_selected_canvas(route_key, widget),
        )

    def _focus_selected_canvas(self, route_key: str, widget: QWidget) -> None:
        """Transfer focus after the originating pointer event has settled."""

        if self._state.active_route_key != route_key:
            return
        widget.setFocus(Qt.FocusReason.OtherFocusReason)


__all__ = ["CanvasHostActivationController"]
