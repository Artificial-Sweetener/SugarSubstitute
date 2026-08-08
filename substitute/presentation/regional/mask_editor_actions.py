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

"""Define and decode intent published by the regional mask editor."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

type RegionalMaskActionKind = Literal["add", "import", "remove", "select"]


@dataclass(frozen=True, slots=True)
class RegionalMaskActionRequest:
    """Describe one validated ordered-mask editor intent."""

    kind: RegionalMaskActionKind
    index: int | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class RegionalMaskActionOutcome:
    """Tell generic Input routing how a regional action changed canvas focus."""

    handled: bool
    activate_canvas: bool = False


def parse_regional_mask_action(action: str) -> RegionalMaskActionRequest | None:
    """Decode one private widget action into validated structured intent."""

    if action == "@region:add":
        return RegionalMaskActionRequest("add")
    select_index = _nonnegative_suffix(action, "@region:select:")
    if select_index is not None:
        return RegionalMaskActionRequest("select", index=select_index)
    remove_index = _nonnegative_suffix(action, "@region:remove:")
    if remove_index is not None:
        return RegionalMaskActionRequest("remove", index=remove_index)
    prefix = "@region:import:"
    if not action.startswith(prefix):
        return None
    try:
        payload = json.loads(action[len(prefix) :])
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or isinstance(payload[0], bool)
        or not isinstance(payload[0], int)
        or payload[0] < 0
        or not isinstance(payload[1], str)
        or not payload[1]
    ):
        return None
    return RegionalMaskActionRequest("import", index=payload[0], path=payload[1])


def _nonnegative_suffix(action: str, prefix: str) -> int | None:
    """Return one decimal action suffix without accepting signs or whitespace."""

    if not action.startswith(prefix):
        return None
    value = action[len(prefix) :]
    return int(value) if value.isdigit() else None


__all__ = [
    "RegionalMaskActionOutcome",
    "RegionalMaskActionRequest",
    "parse_regional_mask_action",
]
