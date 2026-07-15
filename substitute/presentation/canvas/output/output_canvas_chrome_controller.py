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

"""Apply Output canvas floating chrome styles without owning Qt widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OutputCanvasChromeController:
    """Own stylesheet construction for Output canvas floating chrome."""

    surface_rgba: Callable[[], str]
    border_rgba: Callable[[], str]

    def apply_navigation_background_styles(
        self,
        *,
        base_background: object,
        comparison_background: object | None,
    ) -> None:
        """Apply floating navigation background styles to available surfaces."""

        stylesheet = self.navigation_background_stylesheet()
        self.apply_stylesheet(base_background, stylesheet)
        self.apply_stylesheet(comparison_background, stylesheet)

    def navigation_background_stylesheet(self) -> str:
        """Return the current floating navigation background stylesheet."""

        return (
            "\n"
            f"            background-color: {self.surface_rgba()};\n"
            f"            border: 1px solid {self.border_rgba()};\n"
            "            border-radius: 8px;\n"
            "            padding: 0px;\n"
            "        "
        )

    @staticmethod
    def apply_stylesheet(widget: object | None, stylesheet: str) -> None:
        """Apply a stylesheet to a widget-like object when supported."""

        set_stylesheet = getattr(widget, "setStyleSheet", None)
        if callable(set_stylesheet):
            set_stylesheet(stylesheet)


__all__ = [
    "OutputCanvasChromeController",
]
