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

"""Enforce focused ownership of prompt-editor rendering mode."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_rendering_facade_owns_mode_coordination() -> None:
    """Keep display-mode side effects out of the QFluent adapter."""

    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    facade_source = (PROMPT_PRESENTATION_ROOT / "rendering_facade.py").read_text(
        encoding="utf-8"
    )

    for ownership_marker in (
        "bindings.set_exact_source_editing(not enabled)",
        "bindings.set_display_mode(display_mode)",
        "bindings.publish_cursor_position_changed()",
        "bindings.publish_rich_rendering_changed(enabled)",
    ):
        assert ownership_marker in facade_source
        assert ownership_marker not in widget_source

    assert "self._rendering_facade.set_display_mode(display_mode)" in widget_source
    assert "self._rendering_facade.set_rich_rendering_enabled(enabled)" in widget_source
