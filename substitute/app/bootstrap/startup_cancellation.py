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

"""Track startup cancellation state without binding it to Qt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StartupCancellationState:
    """Track whether startup cancellation has been requested."""

    cancelled: bool = False

    def cancel(self) -> None:
        """Record a startup cancellation request."""

        self.cancelled = True


def create_startup_cancellation_state() -> StartupCancellationState:
    """Create the startup cancellation state object."""

    return StartupCancellationState()


__all__ = ["StartupCancellationState", "create_startup_cancellation_state"]
