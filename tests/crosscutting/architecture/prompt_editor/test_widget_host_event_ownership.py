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

"""Enforce focused ownership of prompt-editor host event routing."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_host_event_router_owns_event_precedence() -> None:
    """Keep surface, chrome, and context routing out of the QFluent adapter."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    router_source = (PROMPT_PRESENTATION_ROOT / "host_event_router.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "watched is self.bindings.surface",
        "bindings.handle_focus_in()",
        "bindings.schedule_focus_out_cleanup(",
        "bindings.handle_key_press(",
        "bindings.handle_key_release(",
        "bindings.handle_chrome_event(watched, event)",
        "bindings.record_context_menu_press()",
        "bindings.forward_context_menu(",
    ):
        assert ownership_marker in router_source
        assert ownership_marker not in widget_source

    assert "self._runtime.host.events.route(watched, event)" in widget_source
