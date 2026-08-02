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

"""Define the one material used by floating canvas chrome surfaces."""

from __future__ import annotations

from substitute.presentation.shell.chrome_style import (
    floating_surface_border_rgba,
    floating_surface_rgba,
)

_BORDER_RADIUS = 8


def floating_canvas_surface_stylesheet(
    selector: str | None = None,
    *,
    surface_rgba: str | None = None,
    border_rgba: str | None = None,
) -> str:
    """Build the canonical canvas-chrome surface style for one QSS target."""

    resolved_surface = surface_rgba or floating_surface_rgba()
    resolved_border = border_rgba or floating_surface_border_rgba()
    declarations = (
        f"background-color: {resolved_surface};"
        f"border: 1px solid {resolved_border};"
        f"border-radius: {_BORDER_RADIUS}px;"
        "padding: 0px;"
    )
    return declarations if selector is None else f"{selector} {{{declarations}}}"


__all__ = ["floating_canvas_surface_stylesheet"]
