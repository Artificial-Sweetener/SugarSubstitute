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

"""Own user-selected Ultralytics model-to-thumbnail associations."""

from __future__ import annotations

from collections.abc import Mapping
from threading import RLock
from typing import Protocol

from substitute.application.model_metadata.ultralytics_visual_catalog import (
    bundled_ultralytics_asset_names,
)


class UltralyticsThumbnailAssociationRepository(Protocol):
    """Persist exact backend-value associations as authoritative preferences."""

    def load(self) -> Mapping[str, str]:
        """Return all persisted model-to-asset associations."""

    def save(self, associations: Mapping[str, str]) -> None:
        """Persist the complete association mapping atomically."""


class UltralyticsThumbnailAssociationService:
    """Validate and publish explicit Ultralytics thumbnail selections."""

    def __init__(
        self,
        repository: UltralyticsThumbnailAssociationRepository,
    ) -> None:
        """Load valid saved associations from the preference repository."""

        self._repository = repository
        self._valid_assets = frozenset(bundled_ultralytics_asset_names())
        self._lock = RLock()
        self._associations = self._validated(repository.load())

    def associations(self) -> Mapping[str, str]:
        """Return an immutable snapshot of all current associations."""

        with self._lock:
            return dict(self._associations)

    def asset_for_model(self, backend_value: str) -> str | None:
        """Return the explicit asset selected for one exact backend value."""

        with self._lock:
            return self._associations.get(backend_value)

    def assign(self, backend_value: str, asset_name: str) -> None:
        """Persist one validated exact model-to-library association."""

        if not backend_value.strip():
            raise ValueError("An Ultralytics backend value is required.")
        if asset_name not in self._valid_assets:
            raise ValueError(f"Unknown bundled Ultralytics asset: {asset_name}")
        with self._lock:
            updated = dict(self._associations)
            updated[backend_value] = asset_name
            self._repository.save(updated)
            self._associations = updated

    def _validated(self, associations: Mapping[str, str]) -> dict[str, str]:
        """Discard malformed preference entries without weakening validation."""

        return {
            backend_value: asset_name
            for backend_value, asset_name in associations.items()
            if backend_value.strip() and asset_name in self._valid_assets
        }


__all__ = [
    "UltralyticsThumbnailAssociationRepository",
    "UltralyticsThumbnailAssociationService",
]
