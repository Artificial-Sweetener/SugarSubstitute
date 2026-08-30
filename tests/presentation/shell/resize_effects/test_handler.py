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

"""Tests for shell resize side-effect coordination."""

from __future__ import annotations

from types import SimpleNamespace

import substitute.presentation.shell.session_autosave_controller as session_autosave_controller_module
from substitute.presentation.shell.shell_resize_handler import (
    handle_shell_resize_side_effects,
)


def test_resize_side_effects_debounce_autosave() -> None:
    """Resize side effects should position overlays but defer autosave capture."""

    class _Timer:
        def __init__(self) -> None:
            """Create empty start records."""

            self.start_calls: list[int] = []

        def start(self, delay_ms: int) -> None:
            """Record one start delay."""

            self.start_calls.append(delay_ms)

    timer = _Timer()
    events: list[str] = []
    shell = SimpleNamespace(
        progressOverlay=object(),
        menu_bar=object(),
        progress_overlay_controller=SimpleNamespace(
            position_progress_overlay=lambda: events.append("position")
        ),
        search_overlay_controller=SimpleNamespace(
            position_search_box=lambda: events.append("search")
        ),
        editor_busy=SimpleNamespace(
            refresh_active_surface=lambda: events.append("busy")
        ),
        session_autosave_controller=SimpleNamespace(
            request_resize_autosave=lambda: timer.start(
                session_autosave_controller_module._RESIZE_AUTOSAVE_DEBOUNCE_MS
            )
        ),
        request_session_autosave=lambda: events.append("autosave"),
    )

    handle_shell_resize_side_effects(shell)
    handle_shell_resize_side_effects(shell)

    assert events == ["position", "search", "busy", "position", "search", "busy"]
    assert timer.start_calls == [
        session_autosave_controller_module._RESIZE_AUTOSAVE_DEBOUNCE_MS,
        session_autosave_controller_module._RESIZE_AUTOSAVE_DEBOUNCE_MS,
    ]
