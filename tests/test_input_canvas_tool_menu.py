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

"""Verify Input context menus derive from the live tool palette."""

from __future__ import annotations

from sugarsubstitute_shared.localization import (
    ApplicationMessage,
    ApplicationText,
)

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    ACTIVE_MASK_CAPABILITY,
    INPUT_CANVAS_CONTEXT_TAGS,
    INPUT_IMAGE_CAPABILITY,
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_menu import (
    create_input_canvas_tool_menu,
)
from substitute.presentation.canvas.tools import CanvasToolContext, CanvasToolSurface
from substitute.presentation.widgets.menu_model import MenuItem, MenuSeparator


def _source_text(value: ApplicationText) -> str:
    """Return canonical source copy from one localized menu label."""

    return value.source_text if isinstance(value, ApplicationMessage) else value


def test_input_tool_menu_preserves_palette_order_state_and_sections() -> None:
    """Context menu and strip must never maintain divergent tool inventories."""

    palette = create_input_canvas_tool_system().palette
    palette.set_context(
        CanvasToolContext(
            tags=INPUT_CANVAS_CONTEXT_TAGS,
            capabilities=frozenset({INPUT_IMAGE_CAPABILITY, ACTIVE_MASK_CAPABILITY}),
        )
    )
    assert palette.set_active_tool(InputCanvasToolId.BRUSH)
    requested: list[str] = []
    dock_requests: list[bool] = []

    menu = create_input_canvas_tool_menu(
        palette.snapshot(CanvasToolSurface.TOOL_STRIP),
        tool_requested=requested.append,
        detached=True,
        dock_requested=lambda: dock_requests.append(True),
    )
    items = [entry for entry in menu.entries if isinstance(entry, MenuItem)]
    presentations = palette.snapshot(CanvasToolSurface.TOOL_STRIP)
    tool_items = items[:-1]

    assert [item.data for item in items] == [None] * len(items)
    assert [_source_text(item.label) for item in tool_items] == [
        _source_text(presentation.label) for presentation in presentations
    ]
    assert [item.enabled for item in tool_items] == [
        presentation.enabled for presentation in presentations
    ]
    assert [item.checked for item in tool_items] == [
        presentation.active for presentation in presentations
    ]
    assert sum(isinstance(entry, MenuSeparator) for entry in menu.entries) == 4
    assert all(item.icon is not None for item in tool_items)
    assert _source_text(items[-1].label) == "Redock canvas"

    first_callback = items[0].callback
    dock_callback = items[-1].callback
    assert first_callback is not None
    assert dock_callback is not None
    first_callback()
    dock_callback()
    assert requested == [InputCanvasToolId.MOVE]
    assert dock_requests == [True]
