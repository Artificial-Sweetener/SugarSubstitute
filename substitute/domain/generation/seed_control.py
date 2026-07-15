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

"""Define workflow-owned seed control state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from substitute.domain.common import JsonObject


class SeedMode(StrEnum):
    """Describe whether a seed field should randomize before generation."""

    RANDOM = "random"
    FIXED = "fixed"


@dataclass(frozen=True)
class SeedControlState:
    """Store generation policy for one seed control."""

    mode: SeedMode = SeedMode.RANDOM


def seed_mode_from_value(value: object) -> SeedMode:
    """Return a seed mode, defaulting invalid or missing values to random."""

    if isinstance(value, SeedMode):
        return value
    if not isinstance(value, str):
        return SeedMode.RANDOM
    try:
        return SeedMode(value.strip().lower())
    except ValueError:
        return SeedMode.RANDOM


def seed_control_state_to_json(state: SeedControlState) -> JsonObject:
    """Return a JSON-ready mapping for one seed control state."""

    return {"mode": state.mode.value}


def seed_control_state_from_json(value: object) -> SeedControlState:
    """Build seed control state from decoded JSON, defaulting invalid state."""

    if isinstance(value, SeedControlState):
        return value
    if not isinstance(value, Mapping):
        return SeedControlState()
    return SeedControlState(mode=seed_mode_from_value(value.get("mode")))


__all__ = [
    "SeedControlState",
    "SeedMode",
    "seed_control_state_from_json",
    "seed_control_state_to_json",
    "seed_mode_from_value",
]
