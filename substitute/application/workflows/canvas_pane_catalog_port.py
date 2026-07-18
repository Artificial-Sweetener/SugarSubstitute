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

"""Define the application-facing port for QPane catalog cache access."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import UUID


class CanvasCatalogMutation(Enum):
    """Describe how a catalog cache request changed the pane catalog."""

    ADDED = "added"
    REPLACED = "replaced"
    UNCHANGED = "unchanged"


class CanvasPaneCatalogPort(Protocol):
    """Expose catalog-only QPane cache operations to workflow services."""

    def ensure_image_cached(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> CanvasCatalogMutation:
        """Add or replace one image payload without changing visible routes."""

    def contains(self, image_id: UUID) -> bool:
        """Return whether the pane catalog currently contains image_id."""

    def remove_unreferenced_image(self, image_id: UUID) -> bool:
        """Remove one image payload after the caller proves it is unreferenced."""

    def payload_for_route_preparation(self, image_id: UUID) -> object | None:
        """Return a cached payload for route-preparation hydration only."""

    def snapshot_for_cache_diagnostics(self) -> object | None:
        """Return the raw catalog snapshot for diagnostics-only callers."""


class InputCanvasPaneCatalogPort(CanvasPaneCatalogPort, Protocol):
    """Add restorable source-path lookup required only by the Input canvas."""

    def image_path(self, image_id: UUID) -> Path | None:
        """Return the exact local path cached for one image when available."""


__all__ = [
    "CanvasCatalogMutation",
    "CanvasPaneCatalogPort",
    "InputCanvasPaneCatalogPort",
]
