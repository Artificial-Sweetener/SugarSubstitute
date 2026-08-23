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

"""Verify persistent-cache lifecycle model contracts."""

from pathlib import Path, PurePosixPath

import pytest

from substitute.application.cache_lifecycle import (
    CacheCompatibility,
    CacheDataClass,
    PersistentCacheCatalog,
    PersistentCacheRegistration,
    PreparedCacheCatalog,
    PreparedCacheNamespace,
)


def test_application_version_is_not_a_compatibility_input() -> None:
    """Keep compatible caches reusable across ordinary application releases."""

    compatibility = CacheCompatibility(
        storage_schema="2",
        semantic_epoch=3,
        producer_fingerprint="projection-producer",
    )

    assert (
        compatibility.identifier
        == CacheCompatibility(
            storage_schema="2",
            semantic_epoch=3,
            producer_fingerprint="projection-producer",
        ).identifier
    )


def test_relevant_compatibility_change_selects_a_new_identifier() -> None:
    """Change only the cache whose declared producer contract changed."""

    baseline = CacheCompatibility(
        storage_schema="1",
        semantic_epoch=1,
        producer_fingerprint="producer-a",
    )
    changed = CacheCompatibility(
        storage_schema="1",
        semantic_epoch=1,
        producer_fingerprint="producer-b",
    )

    assert changed.identifier != baseline.identifier


def test_catalog_rejects_overlapping_namespaces() -> None:
    """Prevent two persistent cache owners from sharing directory authority."""

    compatibility = CacheCompatibility(storage_schema="1", semantic_epoch=1)
    with pytest.raises(ValueError, match="overlap"):
        PersistentCacheCatalog(
            registrations=(
                PersistentCacheRegistration(
                    cache_id="model-metadata",
                    namespace=PurePosixPath("model-metadata"),
                    data_class=CacheDataClass.REMOTE_CONTENT,
                    compatibility=compatibility,
                ),
                PersistentCacheRegistration(
                    cache_id="model-thumbnails",
                    namespace=PurePosixPath("model-metadata/thumbnails"),
                    data_class=CacheDataClass.REMOTE_CONTENT,
                    compatibility=compatibility,
                ),
            )
        )


def test_catalog_rejects_unregistered_namespace_access(tmp_path: Path) -> None:
    """Keep cache consumers from bypassing the authoritative registration set."""

    catalog = PreparedCacheCatalog(
        namespaces=(
            PreparedCacheNamespace(
                cache_id="restore-projection",
                path=tmp_path / "restore",
                compatibility_identifier="compatible",
            ),
        )
    )

    with pytest.raises(KeyError, match="not prepared"):
        catalog.namespace("unregistered")
