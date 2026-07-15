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

"""Coordinate shell resize side effects across composed controllers."""

from __future__ import annotations

from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)


def handle_shell_resize_side_effects(shell: object) -> None:
    """Refresh resize-sensitive shell surfaces and request debounced autosave."""

    if hasattr(shell, "progressOverlay") and hasattr(shell, "menu_bar"):
        progress_overlay_controller = getattr(
            shell,
            "progress_overlay_controller",
            None,
        )
        position_progress_overlay = getattr(
            progress_overlay_controller,
            "position_progress_overlay",
            None,
        )
        if callable(position_progress_overlay):
            position_progress_overlay()

    search_overlay_controller = getattr(shell, "search_overlay_controller", None)
    position_search_box = getattr(
        search_overlay_controller,
        "position_search_box",
        None,
    )
    if callable(position_search_box):
        position_search_box()
    else:
        search_overlay_controller_for(shell).position_search_box()

    editor_busy = getattr(shell, "editor_busy", None)
    refresh_active_surface = getattr(editor_busy, "refresh_active_surface", None)
    if callable(refresh_active_surface):
        refresh_active_surface()

    session_autosave = getattr(shell, "session_autosave_controller", None)
    request_resize_autosave = getattr(
        session_autosave,
        "request_resize_autosave",
        None,
    )
    if callable(request_resize_autosave):
        request_resize_autosave()


__all__ = ["handle_shell_resize_side_effects"]
