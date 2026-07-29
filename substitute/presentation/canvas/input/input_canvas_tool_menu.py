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

"""Project the contextual Input tool palette into a context-menu model."""

from __future__ import annotations

from collections.abc import Callable

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.tools import (
    CanvasToolKind,
    CanvasToolPresentation,
)
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)


def create_input_canvas_tool_menu(
    presentations: tuple[CanvasToolPresentation, ...],
    *,
    tool_requested: Callable[[str], None],
    detached: bool,
    dock_requested: Callable[[], None],
) -> MenuModel:
    """Build a menu from the same immutable tool state shown in the strip."""

    entries: list[MenuEntry] = []
    previous_section: str | None = None
    for presentation in presentations:
        if previous_section is not None and presentation.section != previous_section:
            entries.append(MenuSeparator())
        entries.append(
            MenuItem(
                action_id=f"canvas.tool.{presentation.tool_id}",
                label=presentation.label,
                callback=_tool_request_callback(
                    tool_requested,
                    presentation.tool_id,
                ),
                enabled=presentation.enabled,
                checkable=presentation.kind is CanvasToolKind.MODE,
                checked=presentation.active,
                icon=presentation.icon,
            )
        )
        previous_section = presentation.section
    if entries:
        entries.append(MenuSeparator())
    entries.append(
        MenuItem(
            "input_canvas.dock_action",
            app_text("Redock canvas" if detached else "Undock canvas"),
            callback=dock_requested,
        )
    )
    return MenuModel(entries=tuple(entries))


def _tool_request_callback(
    callback: Callable[[str], None],
    tool_id: str,
) -> Callable[[], None]:
    """Bind one immutable tool identity to a menu callback."""

    def request() -> None:
        """Publish the bound tool request."""

        callback(tool_id)

    return request


__all__ = ["create_input_canvas_tool_menu"]
