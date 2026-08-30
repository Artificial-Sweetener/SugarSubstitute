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

"""Tests for cache-only recipe model hash lookup."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem
from substitute.application.recipes import CachedRecipeModelHashLookup
from substitute.domain.model_metadata import (
    CivitaiFile,
    CivitaiModelVersion,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    ThumbnailSelectionStatus,
)


class _Repository:
    """Return fixed model metadata records for lookup tests."""

    def __init__(self, records: tuple[ModelMetadataCacheRecord, ...]) -> None:
        """Store fixed records."""

        self._records = records
        self.list_calls: list[str | None] = []

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return records, optionally filtered by kind."""

        self.list_calls.append(kind)
        return tuple(
            record
            for record in self._records
            if kind is None or record.local.kind == kind
        )


class _RevisionRepository(_Repository):
    """Expose a mutable revision token for shared index cache tests."""

    def __init__(self, records: tuple[ModelMetadataCacheRecord, ...]) -> None:
        """Store fixed records and initialize a revision token."""

        super().__init__(records)
        self.revision = 1

    def replace_records(
        self,
        records: tuple[ModelMetadataCacheRecord, ...],
    ) -> None:
        """Replace records and advance the revision token."""

        self._records = records
        self.revision += 1

    def recipe_hash_revision(
        self, *, kind: str | None = None
    ) -> tuple[int, str | None]:
        """Return the mutable revision token."""

        return self.revision, kind


class _Catalog:
    """Return fixed in-memory catalog rows for lookup tests."""

    def __init__(self, records: dict[str, tuple[ModelCatalogItem, ...]]) -> None:
        """Store catalog rows by kind."""

        self._records = records
        self.cached_calls: list[str] = []

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return fixed cached catalog rows without loading missing kinds."""

        self.cached_calls.append(kind)
        return self._records.get(kind)


def test_cached_recipe_model_hash_lookup_returns_matching_civitai_file_hash() -> None:
    """Eligible records should return the local SHA256 for recipe comments."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    lookup = CachedRecipeModelHashLookup(
        _Repository(
            (_record(kind="checkpoints", value="base.safetensors", sha256=sha256),)
        )
    )

    assert (
        lookup.hash_for_model_value(kind="checkpoints", value="BASE.safetensors")
        == sha256
    )


def test_cached_recipe_model_hash_lookup_skips_not_found_provider() -> None:
    """Provider not-found records should not serialize recipe hash comments."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    lookup = CachedRecipeModelHashLookup(
        _Repository(
            (
                _record(
                    kind="checkpoints",
                    value="base.safetensors",
                    sha256=sha256,
                    provider_status="not-found",
                ),
            )
        )
    )

    assert (
        lookup.hash_for_model_value(kind="checkpoints", value="base.safetensors")
        is None
    )


def test_cached_recipe_model_hash_lookup_requires_provider_file_hash_match() -> None:
    """CivitAI model identity alone should not make a hash comment eligible."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    lookup = CachedRecipeModelHashLookup(
        _Repository(
            (
                _record(
                    kind="checkpoints",
                    value="base.safetensors",
                    sha256=sha256,
                    provider_file_sha256="F" * 64,
                ),
            )
        )
    )

    assert (
        lookup.hash_for_model_value(kind="checkpoints", value="base.safetensors")
        is None
    )


def test_cached_recipe_model_hash_lookup_falls_back_to_cached_catalog_sha() -> None:
    """Renamed cache records should still emit when catalog links value to SHA."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    catalog = _Catalog(
        {
            "diffusion_models": (
                _catalog_item(
                    kind="diffusion_models",
                    value=r"Anima\anima_base_V10.safetensors",
                    sha256=sha256,
                ),
            )
        }
    )
    lookup = CachedRecipeModelHashLookup(
        _Repository(
            (
                _record(
                    kind="diffusion_models",
                    value=r"Anima\anima_base_V100.safetensors",
                    sha256=sha256,
                ),
            )
        ),
        catalog=catalog,
    )

    assert (
        lookup.hash_for_model_value(
            kind="diffusion_models",
            value=r"Anima\anima_base_V10.safetensors",
        )
        == sha256
    )
    assert catalog.cached_calls == ["diffusion_models"]


def test_cached_recipe_model_hash_lookup_does_not_load_uncached_catalog() -> None:
    """Recipe serialization should not refresh model catalogs on cache misses."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    catalog = _Catalog({})
    lookup = CachedRecipeModelHashLookup(
        _Repository(
            (
                _record(
                    kind="diffusion_models",
                    value=r"Anima\renamed.safetensors",
                    sha256=sha256,
                ),
            )
        ),
        catalog=catalog,
    )

    assert (
        lookup.hash_for_model_value(
            kind="diffusion_models",
            value=r"Anima\original.safetensors",
        )
        is None
    )
    assert catalog.cached_calls == ["diffusion_models"]


def test_recipe_model_hash_session_lists_records_once_per_kind() -> None:
    """A lookup session should reuse one eligible-record index per model kind."""

    first_sha256 = "A" * 64
    second_sha256 = "B" * 64
    repository = _Repository(
        (
            _record(kind="loras", value="one.safetensors", sha256=first_sha256),
            _record(kind="loras", value="two.safetensors", sha256=second_sha256),
        )
    )
    session = CachedRecipeModelHashLookup(repository).create_session()

    assert session.hash_for_model_value(kind="loras", value="one.safetensors") == (
        first_sha256
    )
    assert session.hash_for_model_value(kind="loras", value="two.safetensors") == (
        second_sha256
    )
    assert session.hash_for_model_value(kind="loras", value="missing.safetensors") is (
        None
    )
    assert repository.list_calls == ["loras"]


def test_recipe_model_hash_session_keeps_cached_catalog_fallback() -> None:
    """A session should preserve renamed-file lookup through cached catalog rows."""

    sha256 = "ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
    repository = _Repository(
        (
            _record(
                kind="diffusion_models",
                value=r"Anima\renamed.safetensors",
                sha256=sha256,
            ),
        )
    )
    catalog = _Catalog(
        {
            "diffusion_models": (
                _catalog_item(
                    kind="diffusion_models",
                    value=r"Anima\original.safetensors",
                    sha256=sha256,
                ),
            )
        }
    )
    session = CachedRecipeModelHashLookup(repository, catalog=catalog).create_session()

    assert (
        session.hash_for_model_value(
            kind="diffusion_models",
            value=r"Anima\original.safetensors",
        )
        == sha256
    )
    assert (
        session.hash_for_model_value(
            kind="diffusion_models",
            value=r"Anima\missing.safetensors",
        )
        is None
    )
    assert repository.list_calls == ["diffusion_models"]
    assert catalog.cached_calls == ["diffusion_models"]


def test_recipe_model_hash_lookup_reuses_revisioned_index_across_sessions() -> None:
    """Revisioned repositories should avoid rebuilding indexes per serialization."""

    first_sha256 = "A" * 64
    second_sha256 = "B" * 64
    repository = _RevisionRepository(
        (
            _record(kind="loras", value="one.safetensors", sha256=first_sha256),
            _record(kind="loras", value="two.safetensors", sha256=second_sha256),
        )
    )
    lookup = CachedRecipeModelHashLookup(repository)

    first_session = lookup.create_session()
    second_session = lookup.create_session()

    assert (
        first_session.hash_for_model_value(
            kind="loras",
            value="one.safetensors",
        )
        == first_sha256
    )
    assert (
        second_session.hash_for_model_value(
            kind="loras",
            value="two.safetensors",
        )
        == second_sha256
    )
    assert repository.list_calls == ["loras"]


def test_recipe_model_hash_lookup_invalidates_shared_index_on_revision_change() -> None:
    """Shared indexes should rebuild when metadata rows change."""

    first_sha256 = "A" * 64
    second_sha256 = "B" * 64
    repository = _RevisionRepository(
        (_record(kind="loras", value="one.safetensors", sha256=first_sha256),)
    )
    lookup = CachedRecipeModelHashLookup(repository)

    assert lookup.hash_for_model_value(kind="loras", value="one.safetensors") == (
        first_sha256
    )

    repository.replace_records(
        (_record(kind="loras", value="one.safetensors", sha256=second_sha256),)
    )

    assert lookup.hash_for_model_value(kind="loras", value="one.safetensors") == (
        second_sha256
    )
    assert repository.list_calls == ["loras", "loras"]


def _record(
    *,
    kind: str,
    value: str,
    sha256: str,
    provider_status: str = "found",
    provider_file_sha256: str | None = None,
) -> ModelMetadataCacheRecord:
    """Build one metadata cache record for lookup tests."""

    return ModelMetadataCacheRecord(
        schema_version=1,
        local=LocalModelEvidence(
            target_id="target",
            root_id=f"{kind}:0",
            relative_path=value,
            kind=kind,
            value=value,
            display_name=value,
            size_bytes=100,
            modified_at="2026-05-21T00:00:00Z",
            sha256=sha256,
        ),
        provider=(
            _provider(provider_file_sha256 or sha256)
            if provider_status == "found"
            else None
        ),
        provider_status=provider_status,
        thumbnail=None,
        thumbnail_status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
        updated_at="2026-05-21T00:00:00Z",
    )


def _catalog_item(*, kind: str, value: str, sha256: str) -> ModelCatalogItem:
    """Build one picker catalog row for lookup tests."""

    return ModelCatalogItem(
        kind=kind,
        display_name=value,
        display_subtitle=None,
        backend_value=value,
        relative_path=value.replace("\\", "/"),
        folder="",
        basename=value,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=value.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=value.casefold(),
        sha256=sha256,
    )


def _provider(file_sha256: str) -> CivitaiModelVersion:
    """Build provider metadata with one model file."""

    return CivitaiModelVersion(
        model_id=1,
        model_version_id=2,
        model_name="Model",
        model_type="Checkpoint",
        version_name="v1",
        base_model=None,
        trained_words=(),
        description=None,
        version_description=None,
        tags=(),
        creator_username=None,
        creator_image=None,
        nsfw=None,
        nsfw_level=None,
        availability=None,
        files=(
            CivitaiFile(
                file_id=3,
                name="base.safetensors",
                size_kb=1.0,
                file_type="Model",
                download_url="https://civitai.com/api/download/models/2",
                pickle_scan_result="Success",
                virus_scan_result="Success",
                primary=True,
                hashes={"SHA256": file_sha256},
                metadata={},
            ),
        ),
        images=(),
        stats={},
        model_page_url="https://civitai.com/models/1?modelVersionId=2",
        source_url="https://civitai.com/api/v1/model-versions/by-hash/hash",
        fetched_at="2026-05-21T00:00:00Z",
        raw_provider_payload={},
    )
