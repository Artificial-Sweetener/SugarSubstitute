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

"""Define persistence contract for Danbooru viewer preferences."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.danbooru.preferences import DanbooruPreferences


@runtime_checkable
class DanbooruPreferenceRepository(Protocol):
    """Persist Danbooru preference snapshots."""

    def load(self) -> DanbooruPreferences:
        """Load persisted Danbooru preferences."""

    def save(self, preferences: DanbooruPreferences) -> None:
        """Persist one Danbooru preference snapshot."""


__all__ = ["DanbooruPreferenceRepository"]
