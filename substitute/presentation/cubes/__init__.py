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

"""Shared cube presentation primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from substitute.presentation.cubes.cube_card_visual import (
        CubeCardVisual,
        CubeCardVisualState,
    )
    from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard

_EXPORTS = {
    "CubeCardVisual": "substitute.presentation.cubes.cube_card_visual",
    "CubeCardVisualState": "substitute.presentation.cubes.cube_card_visual",
    "CubePlaceholderCard": "substitute.presentation.cubes.cube_placeholder_card",
}


def __getattr__(name: str) -> Any:
    """Load cube widget exports only when a caller asks for them."""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)

    from importlib import import_module

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "CubeCardVisual",
    "CubeCardVisualState",
    "CubePlaceholderCard",
]
