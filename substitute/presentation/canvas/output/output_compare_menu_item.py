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

"""Build the shared Output comparison context-menu command."""

from __future__ import annotations

from collections.abc import Callable

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.widgets.menu_model import MenuItem


def output_compare_menu_item(
    *,
    available: bool,
    enabled: bool,
    set_enabled: Callable[[bool], None],
) -> MenuItem | None:
    """Return the Compare toggle while the active projection supports it."""

    if not available:
        return None
    return MenuItem(
        "output_canvas.compare_outputs",
        app_text("Compare outputs"),
        checkable=True,
        checked=enabled,
        checked_callback=set_enabled,
    )


__all__ = ["output_compare_menu_item"]
