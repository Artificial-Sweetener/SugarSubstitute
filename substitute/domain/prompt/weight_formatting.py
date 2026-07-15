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

"""Format prompt syntax weights with the canonical source-text policy."""

from __future__ import annotations

from decimal import Decimal

PROMPT_WEIGHT_PRECISION = Decimal("0.00")


def format_prompt_weight(weight: Decimal) -> str:
    """Format one prompt weight with fixed two-decimal output."""

    return format(weight.quantize(PROMPT_WEIGHT_PRECISION), "f")


__all__ = ["PROMPT_WEIGHT_PRECISION", "format_prompt_weight"]
