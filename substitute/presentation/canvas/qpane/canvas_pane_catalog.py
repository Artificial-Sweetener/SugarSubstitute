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

"""Centralize QPane catalog cache access without display-route mutations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol, cast
from uuid import UUID

from substitute.application.workflows.canvas_pane_catalog_port import (
    CanvasCatalogMutation,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("presentation.canvas.qpane.canvas_pane_catalog")


class _QPaneCatalogApi(Protocol):
    """Describe the public QPane catalog methods used by the adapter."""

    def addImage(self, image_id: UUID, image: object, path: Path | None) -> None:  # noqa: N802
        """Add or replace one catalog payload."""

    def removeImageByID(self, image_id: UUID) -> None:  # noqa: N802
        """Remove one catalog payload by UUID."""

    def imageIDs(self) -> list[UUID]:  # noqa: N802
        """Return catalog UUIDs."""

    def getCatalogSnapshot(self) -> object:  # noqa: N802
        """Return the QPane catalog snapshot."""


@dataclass(frozen=True, slots=True)
class _PayloadIdentity:
    """Track the payload and catalog path identity cached for one UUID."""

    image_object_id: int
    path: Path | None

    @classmethod
    def from_payload(cls, image: object, path: Path | None) -> "_PayloadIdentity":
        """Build the identity used to suppress duplicate catalog additions."""

        return cls(
            image_object_id=id(image), path=Path(path) if path is not None else None
        )


class CanvasPaneCatalog:
    """Adapt one QPane instance to catalog-only cache operations."""

    def __init__(self, pane: _QPaneCatalogApi | object) -> None:
        """Store one pane and initialize per-UUID payload identity tracking."""

        self._pane = pane
        self._payload_identity_by_id: dict[UUID, _PayloadIdentity] = {}

    def ensure_image_cached(
        self,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> CanvasCatalogMutation:
        """Add or replace an image payload without touching display routes."""

        payload_identity = _PayloadIdentity.from_payload(image, path)
        catalog_contains_image = self.contains(image_id)
        if (
            catalog_contains_image
            and self._payload_identity_by_id.get(image_id) == payload_identity
        ):
            log_debug(
                _LOGGER,
                "QPane catalog image cache already contains payload",
                image_id=image_id,
            )
            return CanvasCatalogMutation.UNCHANGED

        add_image = getattr(self._pane, "addImage", None)
        if not callable(add_image):
            log_warning(
                _LOGGER,
                "QPane catalog image cache add skipped because API is unavailable",
                image_id=image_id,
            )
            return CanvasCatalogMutation.UNCHANGED

        mutation = (
            CanvasCatalogMutation.REPLACED
            if catalog_contains_image
            else CanvasCatalogMutation.ADDED
        )
        started_at = perf_counter()
        add_image(image_id, image, payload_identity.path)
        self._payload_identity_by_id[image_id] = payload_identity
        log_timing(
            _LOGGER,
            "QPane catalog image cache updated",
            started_at=started_at,
            image_id=image_id,
            path=payload_identity.path,
            mutation=mutation.value,
        )
        return mutation

    def contains(self, image_id: UUID) -> bool:
        """Return whether QPane reports image_id in the catalog."""

        catalog_contains_image = self._catalog_contains_image(image_id)
        return catalog_contains_image is True

    def _catalog_contains_image(self, image_id: UUID) -> bool | None:
        """Return catalog availability, or None when the API is unavailable."""

        image_ids = getattr(self._pane, "imageIDs", None)
        if not callable(image_ids):
            return None
        try:
            return image_id in image_ids()
        except (RuntimeError, TypeError, ValueError):
            log_warning(
                _LOGGER,
                "QPane catalog availability query failed",
                image_id=image_id,
            )
            return False

    def remove_unreferenced_image(self, image_id: UUID) -> bool:
        """Remove image_id after the caller has proven no workflow references it."""

        catalog_contains_image = self._catalog_contains_image(image_id)
        if catalog_contains_image is False:
            self._payload_identity_by_id.pop(image_id, None)
            return False
        remove_image = getattr(self._pane, "removeImageByID", None)
        if not callable(remove_image):
            log_warning(
                _LOGGER,
                "QPane catalog image cache removal skipped because API is unavailable",
                image_id=image_id,
            )
            return False
        try:
            remove_image(image_id)
        except (KeyError, RuntimeError, TypeError, ValueError):
            log_warning(
                _LOGGER,
                "QPane catalog image cache removal failed",
                image_id=image_id,
            )
            return False
        self._payload_identity_by_id.pop(image_id, None)
        return True

    def payload_for_route_preparation(self, image_id: UUID) -> object | None:
        """Return a cached payload from the catalog snapshot for route preparation."""

        snapshot = self._catalog_snapshot(
            purpose="route_preparation",
            image_id=image_id,
        )
        if snapshot is None:
            return None
        catalog = getattr(snapshot, "catalog", {})
        entry = catalog.get(image_id) if isinstance(catalog, Mapping) else None
        payload = getattr(entry, "image", None)
        return payload

    def snapshot_for_cache_diagnostics(self) -> object | None:
        """Return QPane's raw catalog snapshot for cache diagnostics."""

        return self._catalog_snapshot(purpose="cache_diagnostics")

    def _catalog_snapshot(
        self,
        *,
        purpose: str,
        image_id: UUID | None = None,
    ) -> object | None:
        """Read QPane's public catalog snapshot for an allowed catalog purpose."""

        snapshot_getter = getattr(self._pane, "getCatalogSnapshot", None)
        if not callable(snapshot_getter):
            return None
        try:
            return cast(object | None, snapshot_getter())
        except (RuntimeError, TypeError, ValueError):
            log_warning(
                _LOGGER,
                "QPane catalog snapshot query failed",
                purpose=purpose,
                image_id=image_id,
            )
            return None


__all__ = ["CanvasPaneCatalog"]
