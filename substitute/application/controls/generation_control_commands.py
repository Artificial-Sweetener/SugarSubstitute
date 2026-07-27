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

"""Define stable generation commands exposed through the Controls page."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GenerationControlCommand(str, Enum):
    """Identify one generation action available to input devices."""

    ACTIVATE = "generation.activate"
    TOGGLE_MODE = "generation.toggle_mode"
    SKIP = "generation.skip"
    STOP = "generation.stop"


@dataclass(frozen=True, slots=True)
class ControlCommandDefinition:
    """Describe one device-neutral control command."""

    command: GenerationControlCommand


def generation_commands() -> tuple[ControlCommandDefinition, ...]:
    """Return generation controls in their Settings display order."""

    return tuple(
        ControlCommandDefinition(command) for command in GenerationControlCommand
    )


__all__ = [
    "ControlCommandDefinition",
    "GenerationControlCommand",
    "generation_commands",
]
