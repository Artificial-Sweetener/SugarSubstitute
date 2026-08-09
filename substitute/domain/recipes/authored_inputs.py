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

"""Represent authored cube inputs admitted to Sugar recipe serialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from substitute.domain.common import JsonValue


@dataclass(frozen=True, slots=True)
class AuthoredRecipeInput:
    """Carry one surface-owned input value into deterministic Sugar formatting."""

    node_key: str
    input_key: str
    value: JsonValue


AuthoredRecipeInputsByAlias: TypeAlias = Mapping[
    str,
    tuple[AuthoredRecipeInput, ...],
]


__all__ = ["AuthoredRecipeInput", "AuthoredRecipeInputsByAlias"]
