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

"""Enforce focused ownership of projection focus-host lifecycle."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_and_mouse_controller_delegate_focus_host_ownership() -> None:
    """Keep focus state out of the surface and pointer host's private contract."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    focus_source = (projection_root / "focus_owner.py").read_text(encoding="utf-8")
    mouse_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "mouse_selection_controller.py"
    ).read_text(encoding="utf-8")

    assert "self._focus_host" not in surface_source
    assert "def eventFilter(" not in surface_source
    assert "_focus_host: QWidget | None" not in mouse_source
    assert "self._ensure_pointer_focus()" in mouse_source
    assert "class PromptProjectionFocusOwner" in focus_source
    assert "focus_host.installEventFilter(self)" in focus_source
