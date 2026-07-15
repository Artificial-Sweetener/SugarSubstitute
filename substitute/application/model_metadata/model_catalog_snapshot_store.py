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

"""Define durable model catalog snapshot storage contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .model_catalog_service import ModelCatalogSnapshot


class ModelCatalogSnapshotStore(Protocol):
    """Persist and load authoritative model catalog snapshots."""

    def load_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return the newest durable authoritative snapshot for one kind."""

    def save_snapshot(self, snapshot: ModelCatalogSnapshot) -> None:
        """Persist one accepted authoritative model catalog snapshot."""


__all__ = ["ModelCatalogSnapshotStore"]
