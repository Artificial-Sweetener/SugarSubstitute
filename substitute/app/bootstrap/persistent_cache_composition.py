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

"""Compose cache-backed repositories exclusively from prepared namespaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from substitute.application.cache_lifecycle import PreparedCacheCatalog
from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_CUBE_CLASSIFICATIONS,
    CACHE_ID_CUBE_ICONS,
    CACHE_ID_DANBOORU_IMAGES,
    CACHE_ID_DANBOORU_METADATA,
    CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
    CACHE_ID_MODEL_METADATA,
    CACHE_ID_MODEL_THUMBNAILS,
)
from substitute.domain.model_metadata import (
    CivitaiImage,
    ThumbnailStoreResult,
)

if TYPE_CHECKING:
    from substitute.app.bootstrap.persistent_cache_runtime import PersistentCacheRuntime
    from substitute.application.model_metadata import ModelCatalogSnapshot
    from substitute.infrastructure.persistence.danbooru_cache_repository import (
        ComposedDanbooruCacheRepository,
    )
    from substitute.infrastructure.persistence.model_metadata_repository import (
        ComposedModelMetadataRepository,
    )
    from substitute.infrastructure.persistence.sqlite_cube_classification_cache import (
        SqliteCubeClassificationCache,
    )
    from substitute.infrastructure.persistence.sqlite_cube_icon_cache import (
        SqliteCubeIconCache,
    )
    from substitute.infrastructure.persistence.sqlite_model_catalog_snapshot_store import (
        SqliteModelCatalogSnapshotStore,
    )
    from substitute.infrastructure.persistence.model_thumbnail_store import (
        ModelThumbnailStore,
    )
    from substitute.infrastructure.persistence.sqlite_model_thumbnail_asset_store import (
        SqliteModelThumbnailAssetStore,
    )


@dataclass(frozen=True, slots=True)
class CubeCacheRepositories:
    """Carry independently governed cube icon and classification caches."""

    icons: SqliteCubeIconCache
    classifications: SqliteCubeClassificationCache


@dataclass(frozen=True, slots=True)
class ModelCacheRepositories:
    """Carry the composed model cache repository and lazy collaborators."""

    metadata: ComposedModelMetadataRepository
    thumbnail_preparer: LazyModelThumbnailStore
    snapshots: LazyModelCatalogSnapshotStore


@dataclass(frozen=True, slots=True)
class RecommendationThumbnailCache:
    """Carry the prepared thumbnail collaborators used during onboarding."""

    preparer: LazyModelThumbnailStore
    assets: SqliteModelThumbnailAssetStore


class LazyModelThumbnailStore:
    """Defer Qt thumbnail preparation imports until thumbnails are requested."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        variant_sizes: tuple[int, ...] = (128, 256, 512),
    ) -> None:
        """Store construction inputs for the concrete thumbnail preparer."""

        self._timeout_seconds = timeout_seconds
        self._variant_sizes = variant_sizes
        self._store: ModelThumbnailStore | None = None

    def cache_thumbnail(
        self,
        *,
        sha256: str,
        image: CivitaiImage,
        selection_policy: str,
    ) -> ThumbnailStoreResult | None:
        """Download and prepare one remote thumbnail through the concrete store."""

        return self._resolve().cache_thumbnail(
            sha256=sha256,
            image=image,
            selection_policy=selection_policy,
        )

    def cache_local_thumbnail(
        self,
        *,
        sha256: str,
        image: object | None,
        source: str,
        source_label: str,
        source_path: str | None = None,
        source_width: int | None = None,
        source_height: int | None = None,
        selection_policy: str = "user_selected_output_canvas",
    ) -> ThumbnailStoreResult | None:
        """Prepare one local thumbnail through the concrete store."""

        return self._resolve().cache_local_thumbnail(
            sha256=sha256,
            image=image,
            source=source,
            source_label=source_label,
            source_path=source_path,
            source_width=source_width,
            source_height=source_height,
            selection_policy=selection_policy,
        )

    def _resolve(self) -> ModelThumbnailStore:
        """Build and cache the concrete thumbnail preparer on first use."""

        if self._store is None:
            from substitute.infrastructure.persistence.model_thumbnail_store import (
                ModelThumbnailStore,
            )

            self._store = ModelThumbnailStore(
                timeout_seconds=self._timeout_seconds,
                variant_sizes=self._variant_sizes,
            )
        return self._store


class LazyModelCatalogSnapshotStore:
    """Defer model catalog snapshot SQLite setup until snapshots are used."""

    def __init__(self, snapshot_root: Path) -> None:
        """Store the prepared snapshot namespace for later construction."""

        self._snapshot_root = snapshot_root
        self._store: SqliteModelCatalogSnapshotStore | None = None

    def load_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Load the newest durable snapshot through the concrete store."""

        return self._resolve().load_snapshot(kind)

    def save_snapshot(self, snapshot: ModelCatalogSnapshot) -> None:
        """Persist a durable snapshot through the concrete store."""

        self._resolve().save_snapshot(snapshot)

    def _resolve(self) -> SqliteModelCatalogSnapshotStore:
        """Build and cache the concrete SQLite snapshot store."""

        if self._store is None:
            from substitute.infrastructure.persistence.sqlite_model_catalog_snapshot_store import (
                SqliteModelCatalogSnapshotStore,
            )

            self._store = SqliteModelCatalogSnapshotStore(self._snapshot_root)
        return self._store


def build_cube_cache_repositories(
    prepared: PreparedCacheCatalog,
) -> CubeCacheRepositories:
    """Build cube caches from their non-overlapping prepared namespaces."""

    from substitute.infrastructure.persistence.sqlite_cube_classification_cache import (
        SqliteCubeClassificationCache,
    )
    from substitute.infrastructure.persistence.sqlite_cube_icon_cache import (
        SqliteCubeIconCache,
    )

    return CubeCacheRepositories(
        icons=SqliteCubeIconCache(prepared.namespace(CACHE_ID_CUBE_ICONS).path),
        classifications=SqliteCubeClassificationCache(
            prepared.namespace(CACHE_ID_CUBE_CLASSIFICATIONS).path
        ),
    )


def build_danbooru_cache_repository(
    prepared: PreparedCacheCatalog,
) -> ComposedDanbooruCacheRepository:
    """Build the Danbooru port from separate metadata and image owners."""

    from substitute.infrastructure.persistence.danbooru_cache_repository import (
        ComposedDanbooruCacheRepository,
    )
    from substitute.infrastructure.persistence.danbooru_cache_store import (
        SqliteDanbooruMetadataStore,
    )
    from substitute.infrastructure.persistence.danbooru_image_cache_store import (
        SqliteDanbooruImageCacheStore,
    )

    return ComposedDanbooruCacheRepository(
        metadata=SqliteDanbooruMetadataStore(
            prepared.namespace(CACHE_ID_DANBOORU_METADATA).path
        ),
        images=SqliteDanbooruImageCacheStore(
            prepared.namespace(CACHE_ID_DANBOORU_IMAGES).path
        ),
    )


def build_model_cache_repositories(
    prepared: PreparedCacheCatalog,
    *,
    thumbnail_policy_key: str,
    thumbnail_timeout_seconds: float = 20.0,
) -> ModelCacheRepositories:
    """Build model cache owners and their lazy producer and snapshot adapters."""

    from substitute.infrastructure.persistence.model_metadata_repository import (
        ComposedModelMetadataRepository,
    )
    from substitute.infrastructure.persistence.sqlite_model_metadata_store import (
        SqliteModelMetadataStore,
    )
    from substitute.infrastructure.persistence.sqlite_model_thumbnail_asset_store import (
        SqliteModelThumbnailAssetStore,
    )

    return ModelCacheRepositories(
        metadata=ComposedModelMetadataRepository(
            metadata=SqliteModelMetadataStore(
                prepared.namespace(CACHE_ID_MODEL_METADATA).path,
                thumbnail_policy_key=thumbnail_policy_key,
            ),
            thumbnails=SqliteModelThumbnailAssetStore(
                prepared.namespace(CACHE_ID_MODEL_THUMBNAILS).path
            ),
        ),
        thumbnail_preparer=LazyModelThumbnailStore(
            timeout_seconds=thumbnail_timeout_seconds
        ),
        snapshots=LazyModelCatalogSnapshotStore(
            prepared.namespace(CACHE_ID_MODEL_CATALOG_SNAPSHOTS).path
        ),
    )


def build_recommendation_thumbnail_cache(
    runtime: PersistentCacheRuntime,
    *,
    thumbnail_timeout_seconds: float = 10.0,
) -> RecommendationThumbnailCache:
    """Build onboarding thumbnail collaborators from the governed namespace."""

    from substitute.infrastructure.persistence.sqlite_model_thumbnail_asset_store import (
        SqliteModelThumbnailAssetStore,
    )

    return RecommendationThumbnailCache(
        preparer=LazyModelThumbnailStore(
            timeout_seconds=thumbnail_timeout_seconds,
            variant_sizes=(1024,),
        ),
        assets=SqliteModelThumbnailAssetStore(
            runtime.prepared.namespace(CACHE_ID_MODEL_THUMBNAILS).path
        ),
    )


__all__ = [
    "CubeCacheRepositories",
    "LazyModelCatalogSnapshotStore",
    "LazyModelThumbnailStore",
    "ModelCacheRepositories",
    "RecommendationThumbnailCache",
    "build_cube_cache_repositories",
    "build_danbooru_cache_repository",
    "build_model_cache_repositories",
    "build_recommendation_thumbnail_cache",
]
