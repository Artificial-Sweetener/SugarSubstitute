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

"""Build tool-group picker menus from immutable slot presentation."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.widgets.menu_model import MenuItem, MenuModel

from .layout_projection import CanvasToolSlotPresentation


def create_canvas_tool_group_menu(
    slot: CanvasToolSlotPresentation,
    *,
    member_requested: Callable[[str], None],
) -> MenuModel:
    """Build a localized member picker without giving the menu durable state."""

    return MenuModel(
        entries=tuple(
            MenuItem(
                action_id=f"canvas.tool.group.{slot.slot_id}.{member.tool_id}",
                label=member.label,
                callback=_member_callback(member_requested, member.tool_id),
                enabled=member.enabled,
                checkable=True,
                checked=member.tool_id == slot.current.tool_id,
                icon=member.icon,
            )
            for member in slot.members
        )
    )


def _member_callback(
    callback: Callable[[str], None],
    tool_id: str,
) -> Callable[[], None]:
    """Bind one stable tool identity to a menu callback."""

    def request() -> None:
        """Publish the bound group-member request."""

        callback(tool_id)

    return request


__all__ = ["create_canvas_tool_group_menu"]
