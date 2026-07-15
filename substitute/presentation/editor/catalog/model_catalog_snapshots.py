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

"""Resolve foreground-safe model rows from prepared catalog snapshots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogLookup,
    ModelCatalogSnapshot,
)


@dataclass(frozen=True, slots=True)
class PreparedModelCatalogRows:
    """Publish prepared model rows and their stable revision identity."""

    items: tuple[ModelCatalogItem, ...] | None
    revision: object | None


def prepared_model_catalog_rows(
    catalog: ModelCatalogLookup,
    kind: str,
) -> PreparedModelCatalogRows:
    """Return the best local model snapshot without backend or network access.

    In-memory canonical state has precedence over the durable authoritative
    snapshot. Persisted metadata is the final startup presentation fallback when
    no authoritative snapshot has been produced yet.
    """

    snapshot_nowait = cast(
        Callable[[str], ModelCatalogSnapshot | None] | None,
        getattr(catalog, "cached_snapshot_nowait", None),
    )
    if callable(snapshot_nowait):
        snapshot = snapshot_nowait(kind)
        if snapshot is not None:
            return _prepared_rows(snapshot)

    cached_snapshot = cast(
        Callable[[str], ModelCatalogSnapshot | None] | None,
        getattr(catalog, "cached_snapshot", None),
    )
    if callable(cached_snapshot):
        snapshot = cached_snapshot(kind)
        if snapshot is not None:
            return _prepared_rows(snapshot)

    durable_snapshot = cast(
        Callable[[str], ModelCatalogSnapshot | None] | None,
        getattr(catalog, "load_durable_snapshot", None),
    )
    if callable(durable_snapshot):
        snapshot = durable_snapshot(kind)
        if snapshot is not None:
            return _prepared_rows(snapshot)

    metadata_snapshot = cast(
        Callable[[str], ModelCatalogSnapshot | None] | None,
        getattr(catalog, "cached_metadata_snapshot_for_kind", None),
    )
    if callable(metadata_snapshot):
        snapshot = metadata_snapshot(kind)
        if snapshot is not None:
            return PreparedModelCatalogRows(
                items=tuple(snapshot.items),
                revision=("metadata_bootstrap", snapshot.generation),
            )

    cached_models = cast(
        Callable[[str], tuple[ModelCatalogItem, ...] | None] | None,
        getattr(catalog, "cached_models", None),
    )
    if callable(cached_models):
        rows = cached_models(kind)
        if rows is not None:
            return PreparedModelCatalogRows(
                items=tuple(rows),
                revision=("cached_models", kind, len(rows)),
            )
    return PreparedModelCatalogRows(items=None, revision=None)


def _prepared_rows(snapshot: ModelCatalogSnapshot) -> PreparedModelCatalogRows:
    """Return prepared rows from one canonical or durable snapshot."""

    return PreparedModelCatalogRows(
        items=tuple(snapshot.items),
        revision=snapshot.generation,
    )


__all__ = ["PreparedModelCatalogRows", "prepared_model_catalog_rows"]
