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

"""Route global shell event-filter work to owning presentation controllers."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent


class ShellEventFilterController:
    """Own shell-level event-filter decisions before Qt fallback handling."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose controllers receive global events."""

        self._shell = shell

    def handle_event_filter_event(self, event: object) -> bool | None:
        """Return an event-filter result, or None when Qt should handle fallback."""

        event_type = getattr(event, "type", None)
        if callable(event_type) and event_type() in {
            QEvent.Type.WindowActivate,
            QEvent.Type.ApplicationActivate,
        }:
            self._shell.cube_library_update_controller.present_pending_updates()
            return False

        search_result = self._shell.search_overlay_controller.handle_event_filter_event(
            event
        )
        if search_result is not None:
            return bool(search_result)
        return None


__all__ = ["ShellEventFilterController"]
