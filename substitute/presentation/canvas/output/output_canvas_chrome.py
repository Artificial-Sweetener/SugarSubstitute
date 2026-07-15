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

"""Wire Output canvas floating chrome to theme refreshes."""

from __future__ import annotations

from collections.abc import Callable

from substitute.presentation.canvas.output.output_canvas_chrome_controller import (
    OutputCanvasChromeController,
)
from substitute.presentation.shell.chrome_style import (
    connect_theme_refresh,
    floating_surface_border_rgba,
    floating_surface_rgba,
)


def install_output_navigation_chrome_theme_refresh(
    *,
    host: object,
    base_background: object,
    comparison_background: object | None,
    connect_refresh: Callable[
        [object, Callable[[], None]], None
    ] = connect_theme_refresh,
    surface_rgba: Callable[[], str] = floating_surface_rgba,
    border_rgba: Callable[[], str] = floating_surface_border_rgba,
) -> None:
    """Apply Output navigation chrome styles now and after theme changes."""

    chrome_controller = OutputCanvasChromeController(
        surface_rgba=surface_rgba,
        border_rgba=border_rgba,
    )

    def apply_theme_styles() -> None:
        """Refresh Output navigation chrome against current theme colors."""

        chrome_controller.apply_navigation_background_styles(
            base_background=base_background,
            comparison_background=comparison_background,
        )

    apply_theme_styles()
    connect_refresh(host, apply_theme_styles)


__all__ = [
    "install_output_navigation_chrome_theme_refresh",
]
