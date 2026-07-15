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

"""Resolve prepared active-model candidates through cached catalog state."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogLookup,
    ModelCatalogSnapshot,
    model_family_associations_for_catalog_item,
)
from substitute.application.user_presets import UserPresetAssociation
from substitute.presentation.editor.catalog.snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.catalog.model_catalog_snapshots import (
    prepared_model_catalog_rows,
)
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
    matching_catalog_item,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.editor.panel.context.active_model_snapshot")


class CachedModelCatalogLookup(ModelCatalogLookup, Protocol):
    """Describe cache-only model catalog reads used by panel preset context."""

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached model rows without loading missing data."""

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached model snapshot without loading data."""

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return an immediately available cached model snapshot."""


@dataclass(frozen=True, slots=True)
class PanelActiveModelSnapshot:
    """Publish one resolved active generative model for preset consumers."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    model_kind: str | None
    model_value: str | None
    catalog_item: ModelCatalogItem | None
    family_associations: tuple[UserPresetAssociation, ...]


class PanelActiveModelSnapshotController:
    """Own cache-only catalog resolution for the active panel model."""

    def __init__(
        self,
        *,
        model_context: PanelActiveModelContextController,
        model_catalog_service: CachedModelCatalogLookup | None,
        panel_context_id_provider: Callable[[], Hashable | None] | None = None,
    ) -> None:
        """Store model context and cache-only catalog collaborators."""

        self._model_context = model_context
        self._model_catalog_service = model_catalog_service
        self._panel_context_id_provider = panel_context_id_provider or (lambda: None)
        self._snapshot = self._build_snapshot(
            model_kind=None,
            model_value=None,
            catalog_item=None,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD),
            catalog_revision=None,
            unavailable_reason=None,
        )

    @property
    def snapshot(self) -> PanelActiveModelSnapshot:
        """Return the last prepared active-model snapshot."""

        return self._snapshot

    def refresh_from_cache(self) -> PanelActiveModelSnapshot:
        """Resolve active model metadata from cached catalog rows only."""

        candidate = self._model_context.current_model()
        if candidate is None:
            return self._publish(
                model_kind=None,
                model_value=None,
                catalog_item=None,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.UNAVAILABLE,
                    unavailable_reason="active_model_unavailable",
                ),
                catalog_revision=None,
                unavailable_reason="active_model_unavailable",
            )
        if self._model_catalog_service is None:
            return self._publish(
                model_kind=candidate.model_kind,
                model_value=candidate.value,
                catalog_item=None,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.UNAVAILABLE,
                    unavailable_reason="model_catalog_unavailable",
                ),
                catalog_revision=None,
                unavailable_reason="model_catalog_unavailable",
            )
        try:
            catalog_items, catalog_revision = self._cached_items(candidate.model_kind)
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to read cached active-model catalog snapshot",
                model_kind=candidate.model_kind,
                error_type=type(error).__name__,
            )
            return self._publish(
                model_kind=candidate.model_kind,
                model_value=candidate.value,
                catalog_item=None,
                status=CatalogSnapshotStatus(
                    CatalogSnapshotReadiness.REFRESH_FAILED,
                    unavailable_reason="model_catalog_unavailable",
                ),
                catalog_revision=None,
                unavailable_reason="model_catalog_unavailable",
            )
        if catalog_items is None:
            return self._publish(
                model_kind=candidate.model_kind,
                model_value=candidate.value,
                catalog_item=None,
                status=CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD),
                catalog_revision=catalog_revision,
                unavailable_reason="model_catalog_cold",
            )
        catalog_item = matching_catalog_item(candidate.value, catalog_items)
        return self._publish(
            model_kind=candidate.model_kind,
            model_value=candidate.value,
            catalog_item=catalog_item,
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            catalog_revision=catalog_revision,
            unavailable_reason=(
                None if catalog_item is not None else "model_catalog_match_unavailable"
            ),
        )

    def _cached_items(
        self,
        model_kind: str,
    ) -> tuple[tuple[ModelCatalogItem, ...] | None, Hashable | None]:
        """Return cached items and revision for one catalog kind."""

        catalog = self._model_catalog_service
        if catalog is None:
            return None, None
        prepared = prepared_model_catalog_rows(catalog, model_kind)
        return prepared.items, prepared.revision

    def _publish(
        self,
        *,
        model_kind: str | None,
        model_value: str | None,
        catalog_item: ModelCatalogItem | None,
        status: CatalogSnapshotStatus,
        catalog_revision: Hashable | None,
        unavailable_reason: str | None,
    ) -> PanelActiveModelSnapshot:
        """Publish one resolved active-model snapshot."""

        self._snapshot = self._build_snapshot(
            model_kind=model_kind,
            model_value=model_value,
            catalog_item=catalog_item,
            status=status,
            catalog_revision=catalog_revision,
            unavailable_reason=unavailable_reason,
        )
        return self._snapshot

    def _build_snapshot(
        self,
        *,
        model_kind: str | None,
        model_value: str | None,
        catalog_item: ModelCatalogItem | None,
        status: CatalogSnapshotStatus,
        catalog_revision: Hashable | None,
        unavailable_reason: str | None,
    ) -> PanelActiveModelSnapshot:
        """Build resolved model state independently of consumer preset policy."""

        context_token = (model_kind, model_value)
        return PanelActiveModelSnapshot(
            identity=CatalogSnapshotIdentity(
                panel_context_id=self._panel_context_id_provider(),
                catalog_revision=catalog_revision,
                prompt_context_token=context_token,
                query_identity=("active_model_context", context_token),
                unavailable_reason=status.unavailable_reason or unavailable_reason,
            ),
            status=status,
            model_kind=model_kind,
            model_value=model_value,
            catalog_item=catalog_item,
            family_associations=model_family_associations_for_catalog_item(
                catalog_item
            ),
        )


__all__ = [
    "CachedModelCatalogLookup",
    "PanelActiveModelSnapshot",
    "PanelActiveModelSnapshotController",
]
