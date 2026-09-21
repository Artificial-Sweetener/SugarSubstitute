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

"""Enforce focused ownership of projection viewport event routing."""

from __future__ import annotations

from .inventory import PROMPT_PRESENTATION_ROOT


def test_surface_delegates_viewport_event_arbitration_to_focused_owner() -> None:
    """Keep viewport event-type policy outside the mounted projection surface."""

    projection_root = PROMPT_PRESENTATION_ROOT / "projection"
    surface_source = (projection_root / "surface.py").read_text(encoding="utf-8")
    router_source = (projection_root / "viewport_event_router.py").read_text(
        encoding="utf-8"
    )

    assert "if watched is self.viewport():" not in surface_source
    assert "router.handle_viewport_event(event)" in surface_source
    assert "installEventFilter(self._input_runtime.viewport_events)" in surface_source
    assert "class PromptProjectionViewportEventRouter" in router_source
    assert "QEvent.Type.DragEnter" in router_source
    assert "QEvent.Type.MouseButtonDblClick" in router_source
