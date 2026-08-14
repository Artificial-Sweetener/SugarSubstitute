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

"""Compose the authoritative persistent-cache registration catalog."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
import sys

from substitute.application.cache_lifecycle import (
    CacheCompatibility,
    CacheDataClass,
    CacheRetentionPolicy,
    PersistentCacheCatalog,
    PersistentCacheRegistration,
)
from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_COMFY_I18N,
    CACHE_ID_CUBE_CLASSIFICATIONS,
    CACHE_ID_CUBE_ICONS,
    CACHE_ID_DANBOORU_IMAGES,
    CACHE_ID_DANBOORU_METADATA,
    CACHE_ID_MANAGED_SETUP_EVIDENCE,
    CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
    CACHE_ID_MODEL_METADATA,
    CACHE_ID_MODEL_THUMBNAILS,
    CACHE_ID_RESTORE_PROJECTION,
)
from substitute.infrastructure.cache_lifecycle import (
    SemanticSourceFingerprintService,
)
from substitute.infrastructure.comfy.managed_setup_cache_storage import (
    build_managed_setup_cache_registration,
)

_CACHE_EMERGENCY_EPOCH = 0


def build_persistent_cache_catalog(
    *,
    source_root: Path | None = None,
) -> PersistentCacheCatalog:
    """Build the complete persistent-cache inventory and compatibility policy."""

    root = source_root.resolve() if source_root is not None else _source_root()
    fingerprints = SemanticSourceFingerprintService()
    rendered_runtime = _rendered_runtime_fingerprint()
    return PersistentCacheCatalog(
        registrations=(
            build_managed_setup_cache_registration(
                source_root=root,
                fingerprints=fingerprints,
            ),
            _derived_registration(
                cache_id=CACHE_ID_RESTORE_PROJECTION,
                namespace="restore/projection",
                storage_schema="3",
                semantic_epoch=1,
                source_root=root,
                fingerprints=fingerprints,
                python_sources=(
                    "substitute/application/workspace_state/restore_projection_models.py",
                    "substitute/application/workspace_state/restore_projection_codec.py",
                    "substitute/application/workspace_state/restored_editor_projection.py",
                    "substitute/application/workspace_state/restore_projection_validation.py",
                ),
                legacy_namespaces=("restore-projection-cache.json",),
            ),
            _rendered_registration(
                cache_id=CACHE_ID_CUBE_ICONS,
                namespace="cube/icons",
                storage_schema="1",
                semantic_epoch=1,
                runtime_fingerprint=rendered_runtime,
                source_root=root,
                fingerprints=fingerprints,
                python_sources=(
                    "substitute/application/ports/cube_icon_cache.py",
                    "substitute/presentation/resources/cube_icon_factory.py",
                    "substitute/shared/qt_thumbnail_codec.py",
                ),
                legacy_namespaces=("cube/cube_icon_cache.sqlite3",),
            ),
            _derived_registration(
                cache_id=CACHE_ID_CUBE_CLASSIFICATIONS,
                namespace="cube/classifications",
                storage_schema="1",
                semantic_epoch=1,
                source_root=root,
                fingerprints=fingerprints,
                python_sources=(
                    "substitute/application/ports/cube_classification_cache.py",
                    "substitute/application/cubes/cube_load_service.py",
                ),
                legacy_namespaces=("cube/cube_classification_cache.sqlite3",),
            ),
            _remote_registration(
                cache_id=CACHE_ID_COMFY_I18N,
                namespace="localization/comfy-i18n",
                storage_schema="2",
                semantic_epoch=1,
                legacy_namespaces=("comfy_i18n",),
            ),
            _remote_registration(
                cache_id=CACHE_ID_DANBOORU_METADATA,
                namespace="danbooru/metadata",
                storage_schema="legacy-implicit-1",
                semantic_epoch=1,
                legacy_namespaces=("danbooru/danbooru_cache.sqlite3",),
            ),
            _remote_registration(
                cache_id=CACHE_ID_DANBOORU_IMAGES,
                namespace="danbooru/images",
                storage_schema="content-addressed-1",
                semantic_epoch=1,
                legacy_namespaces=(
                    "danbooru/danbooru_images",
                    "danbooru/images",
                ),
            ),
            _remote_registration(
                cache_id=CACHE_ID_MODEL_METADATA,
                namespace="models/metadata",
                storage_schema="3",
                semantic_epoch=1,
                legacy_namespaces=("model_metadata/model_metadata.sqlite3",),
            ),
            _rendered_registration(
                cache_id=CACHE_ID_MODEL_THUMBNAILS,
                namespace="models/thumbnails",
                storage_schema="1",
                semantic_epoch=3,
                runtime_fingerprint=rendered_runtime,
                source_root=root,
                fingerprints=fingerprints,
                python_sources=(
                    "substitute/infrastructure/persistence/model_thumbnail_store.py",
                    "substitute/infrastructure/persistence/sqlite_model_thumbnail_asset_store.py",
                    "substitute/infrastructure/persistence/model_metadata_repository.py",
                    "substitute/infrastructure/persistence/thumbnail_banner_cropper.py",
                    "substitute/shared/qt_thumbnail_codec.py",
                ),
                legacy_namespaces=(),
            ),
            _snapshot_registration(
                cache_id=CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
                namespace="models/catalog-snapshots",
                storage_schema="1",
                semantic_epoch=1,
                source_root=root,
                fingerprints=fingerprints,
                python_sources=(
                    "substitute/application/model_metadata/model_catalog_service.py",
                    "substitute/infrastructure/persistence/sqlite_model_catalog_snapshot_store.py",
                ),
                legacy_namespaces=("model_metadata/model_catalog_snapshots.sqlite3",),
            ),
        )
    )


def _derived_registration(
    *,
    cache_id: str,
    namespace: str,
    storage_schema: str,
    semantic_epoch: int,
    source_root: Path,
    fingerprints: SemanticSourceFingerprintService,
    python_sources: tuple[str, ...],
    legacy_namespaces: tuple[str, ...],
) -> PersistentCacheRegistration:
    """Build one source-derived cache registration."""

    return _producer_registration(
        cache_id=cache_id,
        namespace=namespace,
        data_class=CacheDataClass.DERIVED_PROJECTION,
        storage_schema=storage_schema,
        semantic_epoch=semantic_epoch,
        source_root=source_root,
        fingerprints=fingerprints,
        python_sources=python_sources,
        legacy_namespaces=legacy_namespaces,
    )


def _rendered_registration(
    *,
    cache_id: str,
    namespace: str,
    storage_schema: str,
    semantic_epoch: int,
    runtime_fingerprint: str,
    source_root: Path,
    fingerprints: SemanticSourceFingerprintService,
    python_sources: tuple[str, ...],
    legacy_namespaces: tuple[str, ...],
) -> PersistentCacheRegistration:
    """Build one runtime-sensitive rendered cache registration."""

    return _producer_registration(
        cache_id=cache_id,
        namespace=namespace,
        data_class=CacheDataClass.RENDERED_ASSET,
        storage_schema=storage_schema,
        semantic_epoch=semantic_epoch,
        source_root=source_root,
        fingerprints=fingerprints,
        python_sources=python_sources,
        legacy_namespaces=legacy_namespaces,
        runtime_fingerprint=runtime_fingerprint,
    )


def _snapshot_registration(
    *,
    cache_id: str,
    namespace: str,
    storage_schema: str,
    semantic_epoch: int,
    source_root: Path,
    fingerprints: SemanticSourceFingerprintService,
    python_sources: tuple[str, ...],
    legacy_namespaces: tuple[str, ...],
) -> PersistentCacheRegistration:
    """Build one durable remote snapshot registration."""

    return _producer_registration(
        cache_id=cache_id,
        namespace=namespace,
        data_class=CacheDataClass.DURABLE_SNAPSHOT,
        storage_schema=storage_schema,
        semantic_epoch=semantic_epoch,
        source_root=source_root,
        fingerprints=fingerprints,
        python_sources=python_sources,
        legacy_namespaces=legacy_namespaces,
    )


def _producer_registration(
    *,
    cache_id: str,
    namespace: str,
    data_class: CacheDataClass,
    storage_schema: str,
    semantic_epoch: int,
    source_root: Path,
    fingerprints: SemanticSourceFingerprintService,
    python_sources: tuple[str, ...],
    legacy_namespaces: tuple[str, ...],
    runtime_fingerprint: str = "",
) -> PersistentCacheRegistration:
    """Build one registration whose output depends on declared source semantics."""

    producer_fingerprint = fingerprints.fingerprint(
        source_root=source_root,
        python_sources=tuple(Path(path) for path in python_sources),
    )
    return PersistentCacheRegistration(
        cache_id=cache_id,
        namespace=PurePosixPath(namespace),
        data_class=data_class,
        compatibility=CacheCompatibility(
            storage_schema=storage_schema,
            semantic_epoch=semantic_epoch,
            producer_fingerprint=producer_fingerprint,
            runtime_fingerprint=runtime_fingerprint,
            emergency_epoch=_CACHE_EMERGENCY_EPOCH,
        ),
        retention=CacheRetentionPolicy(maximum_generations=3, maximum_age_days=45),
        legacy_namespaces=tuple(PurePosixPath(path) for path in legacy_namespaces),
    )


def _remote_registration(
    *,
    cache_id: str,
    namespace: str,
    storage_schema: str,
    semantic_epoch: int,
    legacy_namespaces: tuple[str, ...],
) -> PersistentCacheRegistration:
    """Build one remote-content registration governed by schema and entry freshness."""

    return PersistentCacheRegistration(
        cache_id=cache_id,
        namespace=PurePosixPath(namespace),
        data_class=CacheDataClass.REMOTE_CONTENT,
        compatibility=CacheCompatibility(
            storage_schema=storage_schema,
            semantic_epoch=semantic_epoch,
            emergency_epoch=_CACHE_EMERGENCY_EPOCH,
        ),
        retention=CacheRetentionPolicy(maximum_generations=2, maximum_age_days=90),
        legacy_namespaces=tuple(PurePosixPath(path) for path in legacy_namespaces),
    )


def _rendered_runtime_fingerprint() -> str:
    """Return runtime identity relevant to persisted Qt-ready pixel buffers."""

    try:
        pyside_version = version("PySide6")
    except PackageNotFoundError:
        pyside_version = "unavailable"
    return f"pyside={pyside_version};platform={sys.platform};byteorder={sys.byteorder}"


def _source_root() -> Path:
    """Return the installed application source root containing `substitute`."""

    return Path(__file__).resolve().parents[3]


__all__ = [
    "CACHE_ID_COMFY_I18N",
    "CACHE_ID_CUBE_CLASSIFICATIONS",
    "CACHE_ID_CUBE_ICONS",
    "CACHE_ID_DANBOORU_IMAGES",
    "CACHE_ID_DANBOORU_METADATA",
    "CACHE_ID_MANAGED_SETUP_EVIDENCE",
    "CACHE_ID_MODEL_CATALOG_SNAPSHOTS",
    "CACHE_ID_MODEL_METADATA",
    "CACHE_ID_MODEL_THUMBNAILS",
    "CACHE_ID_RESTORE_PROJECTION",
    "build_persistent_cache_catalog",
]
