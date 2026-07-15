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

"""Define durable session snapshot persistence contracts."""

from __future__ import annotations

from typing import Protocol

from substitute.domain.session import SessionSnapshot


class SessionSnapshotRepository(Protocol):
    """Persist and recover mutable last-session snapshots."""

    def load(self) -> SessionSnapshot | None:
        """Load the last saved session snapshot when one is available."""

    def save(self, snapshot: SessionSnapshot) -> None:
        """Persist one complete session snapshot atomically."""


__all__ = ["SessionSnapshotRepository"]
