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

"""Own setup operation identity and the boundary between active feedback and history."""

from __future__ import annotations


class SetupOperationLifetime:
    """Admit active updates until settlement while retaining current diagnostic history."""

    def __init__(self) -> None:
        """Initialize an operation that has not issued any work."""
        self._generation: int = 0
        self._active: bool = False

    @property
    def active(self) -> bool:
        """Return whether the current operation still awaits an outcome."""
        return self._active

    def begin(self) -> int:
        """Supersede prior work and return the sole current operation identity."""
        self._generation += 1
        self._active = True
        return self._generation

    def owns(self, generation: int) -> bool:
        """Keep current diagnostics admissible after settlement, until superseded."""
        return generation > 0 and generation == self._generation

    def accepts_progress(self, generation: int) -> bool:
        """Reject active feedback from completed or superseded work."""
        return self._active and self.owns(generation)

    def finish(self, generation: int) -> bool:
        """Settle the current operation exactly once before publishing its outcome."""
        if not self.accepts_progress(generation):
            return False
        self._active = False
        return True
