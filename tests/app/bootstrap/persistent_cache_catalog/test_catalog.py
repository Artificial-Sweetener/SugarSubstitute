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

"""Verify the authoritative application persistent-cache inventory."""

from pathlib import Path

from substitute.app.bootstrap import persistent_cache_catalog
from substitute.app.bootstrap.persistent_cache_catalog import (
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
    build_persistent_cache_catalog,
)
from substitute.application.cache_lifecycle import CacheDataClass

_EXPECTED_CACHE_IDS = {
    CACHE_ID_RESTORE_PROJECTION,
    CACHE_ID_CUBE_ICONS,
    CACHE_ID_CUBE_CLASSIFICATIONS,
    CACHE_ID_COMFY_I18N,
    CACHE_ID_DANBOORU_METADATA,
    CACHE_ID_DANBOORU_IMAGES,
    CACHE_ID_MODEL_METADATA,
    CACHE_ID_MODEL_THUMBNAILS,
    CACHE_ID_MODEL_CATALOG_SNAPSHOTS,
    CACHE_ID_MANAGED_SETUP_EVIDENCE,
}


def test_catalog_is_the_complete_non_overlapping_persistent_cache_inventory() -> None:
    """Keep every active persistent cache under one reviewable authority."""

    catalog = build_persistent_cache_catalog(source_root=_project_root())

    assert {item.cache_id for item in catalog.registrations} == _EXPECTED_CACHE_IDS
    assert len({item.namespace for item in catalog.registrations}) == len(
        catalog.registrations
    )


def test_derived_and_rendered_caches_declare_semantic_producers() -> None:
    """Prevent manually versioned derived output from bypassing smart invalidation."""

    catalog = build_persistent_cache_catalog(source_root=_project_root())

    for registration in catalog.registrations:
        if registration.data_class is CacheDataClass.REMOTE_CONTENT:
            continue
        assert registration.compatibility.producer_fingerprint


def test_rendered_caches_declare_runtime_compatibility() -> None:
    """Keep persisted Qt-ready buffers scoped to compatible runtimes."""

    catalog = build_persistent_cache_catalog(source_root=_project_root())

    rendered = tuple(
        item
        for item in catalog.registrations
        if item.data_class is CacheDataClass.RENDERED_ASSET
    )
    assert {item.cache_id for item in rendered} == {
        CACHE_ID_CUBE_ICONS,
        CACHE_ID_MODEL_THUMBNAILS,
    }
    assert all(item.compatibility.runtime_fingerprint for item in rendered)


def _project_root() -> Path:
    """Return the checkout root containing application producer sources."""

    return Path(persistent_cache_catalog.__file__).parents[3]
