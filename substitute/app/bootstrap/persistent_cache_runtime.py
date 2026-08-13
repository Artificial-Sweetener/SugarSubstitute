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

"""Own process-lifetime persistent-cache preparation and fallback storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute._version import __version__
from substitute.app.bootstrap.persistent_cache_catalog import (
    build_persistent_cache_catalog,
)
from substitute.application.cache_lifecycle import (
    PersistentCacheCatalog,
    PersistentCachePreparationService,
    PreparedCacheCatalog,
)
from substitute.infrastructure.cache_lifecycle import FilePersistentCacheStorage


@dataclass(frozen=True, slots=True)
class PersistentCacheRuntime:
    """Retain prepared namespaces and temporary fallback lifetime ownership."""

    catalog: PersistentCacheCatalog
    prepared: PreparedCacheCatalog
    storage: FilePersistentCacheStorage

    def close(self) -> None:
        """Release process-lifetime nonpersistent fallback storage."""

        self.storage.close()


def prepare_persistent_cache_runtime(
    cache_root: Path,
    *,
    installation_root: Path | None = None,
    legacy_model_metadata_root: Path | None = None,
    source_root: Path | None = None,
    application_version: str = __version__,
) -> PersistentCacheRuntime:
    """Prepare the complete cache catalog before constructing repositories."""

    catalog = build_persistent_cache_catalog(source_root=source_root)
    storage = FilePersistentCacheStorage(
        cache_root,
        application_version=application_version,
        installation_root=installation_root,
        legacy_model_metadata_root=legacy_model_metadata_root,
    )
    prepared = PersistentCachePreparationService(
        catalog=catalog,
        storage=storage,
    ).prepare()
    return PersistentCacheRuntime(
        catalog=catalog,
        prepared=prepared,
        storage=storage,
    )


__all__ = ["PersistentCacheRuntime", "prepare_persistent_cache_runtime"]
