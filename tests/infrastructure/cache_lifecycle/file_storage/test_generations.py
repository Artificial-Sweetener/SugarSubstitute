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

"""Verify persistent cache generation selection and recovery on real files."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path, PurePosixPath

from substitute.application.cache_lifecycle import (
    CacheCompatibility,
    CacheDataClass,
    PersistentCacheCatalog,
    PersistentCacheRegistration,
)
from substitute.infrastructure.cache_lifecycle import FilePersistentCacheStorage

_NOW = datetime(2026, 8, 12, 18, 30, tzinfo=UTC)


def test_compatible_generation_survives_application_version_change(
    tmp_path: Path,
) -> None:
    """Reuse proven data when only the diagnostic application version changes."""

    catalog = _catalog(restore_producer="producer-a")
    first_storage = _storage(tmp_path, application_version="0.19.2")
    first = first_storage.prepare(catalog).namespace("restore-projection")
    (first.path / "payload.json").write_text("cached", encoding="utf-8")

    second_storage = _storage(tmp_path, application_version="0.20.0")
    second = second_storage.prepare(catalog).namespace("restore-projection")

    assert second.path == first.path
    assert (second.path / "payload.json").read_text(encoding="utf-8") == "cached"
    manifest = json.loads(
        (tmp_path / "persistent-cache-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["application_version"] == "0.20.0"


def test_relevant_change_selects_only_its_owner_generation(tmp_path: Path) -> None:
    """Preserve unrelated persistent caches after one producer changes."""

    baseline = _storage(tmp_path).prepare(_catalog(restore_producer="producer-a"))
    baseline_restore = baseline.namespace("restore-projection")
    baseline_remote = baseline.namespace("danbooru-content")
    (baseline_restore.path / "projection.json").write_text("old", encoding="utf-8")
    (baseline_remote.path / "remote.db").write_text("remote", encoding="utf-8")

    changed = _storage(tmp_path).prepare(_catalog(restore_producer="producer-b"))

    assert changed.namespace("restore-projection").path != baseline_restore.path
    assert not (
        changed.namespace("restore-projection").path / "projection.json"
    ).exists()
    assert changed.namespace("danbooru-content").path == baseline_remote.path
    assert (changed.namespace("danbooru-content").path / "remote.db").read_text(
        encoding="utf-8"
    ) == "remote"


def test_switching_back_reuses_earlier_compatible_generation(tmp_path: Path) -> None:
    """Make development branch switching reuse its earlier proven cache."""

    first = (
        _storage(tmp_path)
        .prepare(_catalog(restore_producer="branch-a"))
        .namespace("restore-projection")
    )
    (first.path / "projection.json").write_text("branch-a", encoding="utf-8")
    second = (
        _storage(tmp_path)
        .prepare(_catalog(restore_producer="branch-b"))
        .namespace("restore-projection")
    )

    returned = (
        _storage(tmp_path)
        .prepare(_catalog(restore_producer="branch-a"))
        .namespace("restore-projection")
    )

    assert second.path != first.path
    assert returned.path == first.path
    assert (returned.path / "projection.json").read_text(encoding="utf-8") == "branch-a"


def test_corrupt_generation_marker_is_quarantined_before_reuse(
    tmp_path: Path,
) -> None:
    """Prevent unproven generation content from reaching a cache consumer."""

    catalog = _catalog(restore_producer="producer-a")
    first = _storage(tmp_path).prepare(catalog).namespace("restore-projection")
    (first.path / "payload.json").write_text("must-not-reuse", encoding="utf-8")
    (first.path / "generation.json").write_text("not-json", encoding="utf-8")

    repaired = _storage(tmp_path).prepare(catalog).namespace("restore-projection")

    assert repaired.path == first.path
    assert not (repaired.path / "payload.json").exists()
    quarantined = tuple(
        (tmp_path / "managed" / "quarantine" / "restore-projection").iterdir()
    )
    assert len(quarantined) == 1
    assert (quarantined[0] / "payload.json").read_text(encoding="utf-8") == (
        "must-not-reuse"
    )


def test_corrupt_root_manifest_does_not_discard_verified_generation(
    tmp_path: Path,
) -> None:
    """Rebuild diagnostic metadata from valid per-generation proof."""

    catalog = _catalog(restore_producer="producer-a")
    first = _storage(tmp_path).prepare(catalog).namespace("restore-projection")
    (first.path / "payload.json").write_text("verified", encoding="utf-8")
    (tmp_path / "persistent-cache-manifest.json").write_text(
        "truncated{",
        encoding="utf-8",
    )

    prepared = _storage(tmp_path).prepare(catalog).namespace("restore-projection")

    assert prepared.path == first.path
    assert (prepared.path / "payload.json").read_text(encoding="utf-8") == "verified"
    assert len(tuple(tmp_path.glob("persistent-cache-manifest.json.corrupt-*"))) == 1


def test_unavailable_cache_root_uses_nonpersistent_isolated_namespaces(
    tmp_path: Path,
) -> None:
    """Keep disposable cache IO failure from aborting application startup."""

    unavailable_root = tmp_path / "cache-root-is-a-file"
    unavailable_root.write_text("occupied", encoding="utf-8")
    storage = _storage(unavailable_root)
    try:
        prepared = storage.prepare(_catalog(restore_producer="producer-a"))

        assert not prepared.namespace("restore-projection").persistent
        assert not prepared.namespace("danbooru-content").persistent
        assert prepared.namespace("restore-projection").path.is_dir()
    finally:
        storage.close()


def test_retention_prunes_only_old_marker_proven_generations(tmp_path: Path) -> None:
    """Bound branch generations without deleting unproven namespace content."""

    first = (
        _storage(tmp_path, now=_NOW)
        .prepare(_catalog(restore_producer="producer-1"))
        .namespace("restore-projection")
    )
    unproven = first.path.parent / "manual-content"
    unproven.mkdir()
    (unproven / "keep.txt").write_text("unknown", encoding="utf-8")
    _storage(tmp_path, now=_NOW + timedelta(days=1)).prepare(
        _catalog(restore_producer="producer-2")
    )
    third = (
        _storage(tmp_path, now=_NOW + timedelta(days=2))
        .prepare(_catalog(restore_producer="producer-3"))
        .namespace("restore-projection")
    )

    assert not first.path.exists()
    assert third.path.exists()
    assert (unproven / "keep.txt").read_text(encoding="utf-8") == "unknown"


def _storage(
    cache_root: Path,
    *,
    application_version: str = "0.20.0",
    now: datetime = _NOW,
) -> FilePersistentCacheStorage:
    """Build deterministic real-file lifecycle storage for one test root."""

    return FilePersistentCacheStorage(
        cache_root,
        application_version=application_version,
        clock=lambda: now,
    )


def _catalog(*, restore_producer: str) -> PersistentCacheCatalog:
    """Build two independently compatible cache registrations."""

    return PersistentCacheCatalog(
        registrations=(
            PersistentCacheRegistration(
                cache_id="restore-projection",
                namespace=PurePosixPath("restore/projection"),
                data_class=CacheDataClass.DERIVED_PROJECTION,
                compatibility=CacheCompatibility(
                    storage_schema="2",
                    semantic_epoch=3,
                    producer_fingerprint=restore_producer,
                ),
            ),
            PersistentCacheRegistration(
                cache_id="danbooru-content",
                namespace=PurePosixPath("danbooru/content"),
                data_class=CacheDataClass.REMOTE_CONTENT,
                compatibility=CacheCompatibility(
                    storage_schema="1",
                    semantic_epoch=1,
                ),
            ),
        )
    )
