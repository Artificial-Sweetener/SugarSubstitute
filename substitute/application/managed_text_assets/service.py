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

"""Define the managed text asset application service contract."""

from __future__ import annotations

from typing import Protocol

from .models import (
    CreateManagedTextAssetRequest,
    ManagedTextAsset,
    RenameManagedTextAssetRequest,
)


class ManagedTextAssetService(Protocol):
    """Expose backend-neutral text asset editing operations."""

    def list_assets(self) -> tuple[ManagedTextAsset, ...]:
        """Return every asset available for management."""

    def read_asset_text(self, asset_id: str) -> str:
        """Return the editable source text for one asset."""

    def save_asset_text(self, asset_id: str, text: str) -> ManagedTextAsset:
        """Persist source text for one asset and return refreshed metadata."""

    def create_asset(
        self,
        request: CreateManagedTextAssetRequest,
    ) -> ManagedTextAsset:
        """Create one asset and return its metadata."""

    def rename_asset(
        self,
        request: RenameManagedTextAssetRequest,
    ) -> ManagedTextAsset:
        """Rename one asset and return refreshed metadata."""

    def delete_asset(self, asset_id: str) -> None:
        """Delete one asset."""

    def set_asset_enabled(self, asset_id: str, enabled: bool) -> ManagedTextAsset:
        """Set optional participation state for one asset."""

    def refresh(self) -> None:
        """Refresh backend caches used by managed assets."""


__all__ = ["ManagedTextAssetService"]
