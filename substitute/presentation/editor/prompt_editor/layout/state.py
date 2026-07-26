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

"""Own the atomically published immutable prompt-layout output."""

from __future__ import annotations

from .contracts import (
    PromptLayoutDamage,
    PromptLayoutOutcome,
    PromptLayoutOutput,
    PromptLayoutStatus,
)


class PromptLayoutState:
    """Hold one current layout output without owning layout algorithms."""

    __slots__ = ("_current",)

    def __init__(self, initial: PromptLayoutOutput) -> None:
        """Publish the initial complete layout output."""

        self._current = initial

    @property
    def current(self) -> PromptLayoutOutput:
        """Return the exact immutable output visible to downstream consumers."""

        return self._current

    def publish(self, outcome: PromptLayoutOutcome) -> PromptLayoutDamage:
        """Atomically adopt one complete applied engine outcome."""

        if (
            outcome.status is not PromptLayoutStatus.APPLIED
            or outcome.output is None
            or outcome.damage is None
        ):
            raise ValueError("layout state can publish only complete applied outcomes")
        self._current = outcome.output
        return outcome.damage

    def restore(self, output: PromptLayoutOutput) -> None:
        """Atomically restore one previously validated immutable output."""

        self._current = output


__all__ = ["PromptLayoutState"]
