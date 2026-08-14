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

"""Prepare the governed managed-setup evidence cache namespace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from substitute._version import __version__
from substitute.application.cache_lifecycle import (
    CacheCompatibility,
    CacheDataClass,
    CacheRetentionPolicy,
    PersistentCacheCatalog,
    PersistentCacheRegistration,
)
from substitute.application.cache_lifecycle.cache_ids import (
    CACHE_ID_MANAGED_SETUP_EVIDENCE,
)
from substitute.infrastructure.cache_lifecycle import (
    FilePersistentCacheStorage,
    SemanticSourceFingerprintService,
)
from substitute.infrastructure.comfy.managed_setup_evidence import (
    load_json_object,
    write_json_object_atomic,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("infrastructure.comfy.managed_setup_cache_storage")
_CACHE_ROOT = "cache"
_LEGACY_RECORD_NAME = "managed_setup_freshness.json"
_RECORD_NAME = "record.json"


@dataclass(slots=True)
class ManagedSetupCacheSession:
    """Keep one prepared setup-evidence namespace alive for a transaction."""

    record_path: Path
    _storage: FilePersistentCacheStorage

    def close(self) -> None:
        """Release a temporary fallback namespace after the transaction."""

        self._storage.close()


def build_managed_setup_cache_registration(
    *,
    source_root: Path,
    fingerprints: SemanticSourceFingerprintService,
) -> PersistentCacheRegistration:
    """Declare setup evidence compatibility, retention, and source ownership."""

    producer_fingerprint = fingerprints.fingerprint(
        source_root=source_root,
        python_sources=(
            Path("substitute/infrastructure/comfy/managed_setup_freshness_cache.py"),
            Path("substitute/infrastructure/comfy/managed_setup_freshness_inputs.py"),
            Path(
                "substitute/infrastructure/comfy/managed_runtime_configuration_codec.py"
            ),
        ),
    )
    return PersistentCacheRegistration(
        cache_id=CACHE_ID_MANAGED_SETUP_EVIDENCE,
        namespace=PurePosixPath("managed-comfy/setup-evidence"),
        data_class=CacheDataClass.DERIVED_PROJECTION,
        compatibility=CacheCompatibility(
            storage_schema="5",
            semantic_epoch=1,
            producer_fingerprint=producer_fingerprint,
            emergency_epoch=0,
        ),
        retention=CacheRetentionPolicy(maximum_generations=3, maximum_age_days=45),
    )


def prepare_managed_setup_cache(workspace: Path) -> ManagedSetupCacheSession:
    """Prepare setup evidence beneath the managed workspace cache root."""

    source_root = Path(__file__).resolve().parents[3]
    fingerprints = SemanticSourceFingerprintService()
    registration = build_managed_setup_cache_registration(
        source_root=source_root,
        fingerprints=fingerprints,
    )
    storage = FilePersistentCacheStorage(
        workspace / ".substitute" / _CACHE_ROOT,
        application_version=__version__,
    )
    prepared = storage.prepare(PersistentCacheCatalog(registrations=(registration,)))
    record_path = (
        prepared.namespace(CACHE_ID_MANAGED_SETUP_EVIDENCE).path / _RECORD_NAME
    )
    _adopt_legacy_record(workspace=workspace, record_path=record_path)
    return ManagedSetupCacheSession(record_path=record_path, _storage=storage)


def _adopt_legacy_record(*, workspace: Path, record_path: Path) -> None:
    """Copy one verified legacy cache record into its catalog-owned namespace."""

    if record_path.exists():
        return
    legacy_path = workspace / ".substitute" / _LEGACY_RECORD_NAME
    payload = load_json_object(legacy_path)
    if payload is None:
        return
    try:
        write_json_object_atomic(record_path, payload)
    except OSError as error:
        log_warning(
            _LOGGER,
            "Managed setup cache migration failed; treating evidence as absent.",
            legacy_path=legacy_path,
            error=repr(error),
        )
        return
    log_info(
        _LOGGER,
        "Adopted legacy managed setup evidence into the governed cache.",
        legacy_path=legacy_path,
    )


__all__ = [
    "ManagedSetupCacheSession",
    "build_managed_setup_cache_registration",
    "prepare_managed_setup_cache",
]
