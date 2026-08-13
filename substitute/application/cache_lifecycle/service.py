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

"""Coordinate persistent-cache preparation before repositories are opened."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.cache_lifecycle.models import (
    PersistentCacheCatalog,
    PreparedCacheCatalog,
)
from substitute.application.cache_lifecycle.ports import PersistentCacheStorage


@dataclass(frozen=True, slots=True)
class PersistentCachePreparationService:
    """Prepare the authoritative cache catalog through its storage boundary."""

    catalog: PersistentCacheCatalog
    storage: PersistentCacheStorage

    def prepare(self) -> PreparedCacheCatalog:
        """Prepare every registered cache before any consumer can open it."""

        return self.storage.prepare(self.catalog)


__all__ = ["PersistentCachePreparationService"]
