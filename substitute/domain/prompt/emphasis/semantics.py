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

"""Define canonical prompt-emphasis semantics."""

from __future__ import annotations

from decimal import Decimal

EDITOR_EMPHASIS_ADJUSTMENT_STEP = Decimal("0.05")
EDITOR_DEFAULT_POSITIVE_EMPHASIS = Decimal("1.05")
COMFY_IMPLICIT_EMPHASIS_MULTIPLIER = Decimal("1.1")


def implicit_emphasis_weight(depth: int) -> Decimal:
    """Return the exact ComfyUI multiplier for one implicit nesting depth."""

    if depth < 1:
        raise ValueError("Implicit emphasis depth must be positive.")
    return COMFY_IMPLICIT_EMPHASIS_MULTIPLIER**depth


def format_generated_emphasis_weight(weight: Decimal) -> str:
    """Format generated emphasis exactly with at least two decimal places."""

    text = format(weight, "f")
    integer, separator, fractional = text.partition(".")
    if not separator:
        return f"{integer}.00"
    return f"{integer}.{fractional.ljust(2, '0')}"


__all__ = [
    "COMFY_IMPLICIT_EMPHASIS_MULTIPLIER",
    "EDITOR_DEFAULT_POSITIVE_EMPHASIS",
    "EDITOR_EMPHASIS_ADJUSTMENT_STEP",
    "format_generated_emphasis_weight",
    "implicit_emphasis_weight",
]
