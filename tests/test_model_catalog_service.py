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

"""Tests for generic model metadata catalog projection."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Thread

from substitute.application.model_metadata import (
    ModelCatalogService,
    ModelCatalogSnapshot,
    ModelThumbnailVariant,
)
from substitute.infrastructure.persistence import SqliteModelCatalogSnapshotStore
from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    BackendFingerprint,
    BackendFingerprintJob,
    BackendLocalPreview,
    BackendModelCatalogEntry,
    BackendModelFile,
    BackendModelSource,
    BackendSidecar,
    CivitaiModelVersion,
    FingerprintStatus,
    JobStatus,
    LocalModelEvidence,
    ModelMetadataCacheRecord,
    STANDARD_THUMBNAIL_ROLE,
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
)


class _FakeBackend:
    """Return deterministic backend model catalog entries."""

    def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
        """Store fake entries for requested kind filtering."""

        self.entries = entries
        self.list_model_calls: list[tuple[tuple[str, ...], bool]] = []

    def get_capabilities(self) -> None:
        """Return no capabilities because catalog tests do not use this method."""

        return None

    def refresh_fingerprints(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
    ) -> BackendFingerprintJob:
        """Return an empty fingerprint job because catalog tests do not use this method."""

        _ = entries
        return BackendFingerprintJob(
            job_id="unused",
            status=JobStatus.COMPLETE,
            entries=(),
        )

    def get_fingerprint_job(self, job_id: str) -> BackendFingerprintJob | None:
        """Return no fingerprint job because catalog tests do not use this method."""

        _ = job_id
        return None

    def list_models(
        self,
        kinds: tuple[str, ...],
        *,
        refresh: bool = False,
    ) -> tuple[BackendModelCatalogEntry, ...]:
        """Return fake model entries for the requested model kinds."""

        self.list_model_calls.append((kinds, refresh))
        return tuple(entry for entry in self.entries if entry.kind in kinds)


class _FakeCatalog:
    """Return deterministic cached metadata records."""

    def __init__(self, records: tuple[ModelMetadataCacheRecord, ...]) -> None:
        """Store fake records for requested kind filtering."""

        self.records = records

    def list_records(
        self,
        *,
        kind: str | None = None,
    ) -> tuple[ModelMetadataCacheRecord, ...]:
        """Return fake metadata records filtered by kind."""

        if kind is None:
            return self.records
        return tuple(record for record in self.records if record.local.kind == kind)


def test_model_catalog_lists_model_kinds_separately(tmp_path: Path) -> None:
    """Catalog reads should stay scoped to the requested backend model kind."""

    backend = _FakeBackend(
        (
            _entry("checkpoints", "models/checkpoint.safetensors", "ABC"),
            _entry("loras", "models/lora.safetensors", "DEF"),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    checkpoints = service.list_models("checkpoints")
    loras = service.list_models("loras")

    assert [item.backend_value for item in checkpoints] == [
        "models/checkpoint.safetensors"
    ]
    assert [item.backend_value for item in loras] == ["models/lora.safetensors"]
    assert backend.list_model_calls == [
        (("checkpoints",), False),
        (("loras",), False),
    ]
    assert service.list_models("checkpoints") == checkpoints
    assert backend.list_model_calls == [
        (("checkpoints",), False),
        (("loras",), False),
    ]


def test_model_catalog_cached_models_never_loads_missing_kind(tmp_path: Path) -> None:
    """Cached snapshot reads should not touch the backend when data is absent."""

    backend = _FakeBackend(
        (_entry("checkpoints", "models/checkpoint.safetensors", "ABC"),)
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    assert service.cached_models("checkpoints") is None
    assert backend.list_model_calls == []

    checkpoints = service.list_models("checkpoints")

    assert service.cached_models("checkpoints") == checkpoints
    assert service.cached_snapshot("checkpoints") == ModelCatalogSnapshot(
        kind="checkpoints",
        items=checkpoints,
        generation=0,
    )


def test_model_catalog_snapshot_loads_are_single_flight(tmp_path: Path) -> None:
    """Concurrent snapshot reads should share one backend load per cold kind."""

    class _BlockingBackend(_FakeBackend):
        """Block the first backend call until the test has queued a waiter."""

        def __init__(self, entries: tuple[BackendModelCatalogEntry, ...]) -> None:
            """Store fake entries and load coordination events."""

            super().__init__(entries)
            self.started = Event()
            self.release = Event()

        def list_models(
            self,
            kinds: tuple[str, ...],
            *,
            refresh: bool = False,
        ) -> tuple[BackendModelCatalogEntry, ...]:
            """Block while a concurrent snapshot request enters the service."""

            self.started.set()
            assert self.release.wait(timeout=5)
            return super().list_models(kinds, refresh=refresh)

    backend = _BlockingBackend(
        (_entry("checkpoints", "models/checkpoint.safetensors", "ABC"),)
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    snapshots: list[ModelCatalogSnapshot] = []
    errors: list[BaseException] = []

    def load_snapshot() -> None:
        """Load one checkpoint snapshot from a worker thread."""

        try:
            snapshots.append(service.snapshot_for_kind("checkpoints"))
        except BaseException as error:  # pragma: no cover - re-raised below
            errors.append(error)

    first = Thread(target=load_snapshot, name="catalog-test-first")
    second = Thread(target=load_snapshot, name="catalog-test-second")
    first.start()
    assert backend.started.wait(timeout=5)
    second.start()
    backend.release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    if errors:
        raise AssertionError(errors) from errors[0]
    assert len(snapshots) == 2
    assert snapshots[0] is snapshots[1]
    assert backend.list_model_calls == [(("checkpoints",), False)]


def test_model_catalog_builds_cache_only_snapshot_without_backend(
    tmp_path: Path,
) -> None:
    """Metadata-cache snapshots should expose thumbnails before Backend is ready."""

    backend = _FakeBackend(())
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(
            (
                _record(
                    kind="loras",
                    value="cached/style.safetensors",
                    sha256="ABC",
                    model_name="Cached Style",
                    version_name="v1",
                ),
            )
        ),
        model_metadata_root=tmp_path,
    )

    snapshot = service.cached_metadata_snapshot_for_kind("loras")

    assert backend.list_model_calls == []
    assert snapshot.kind == "loras"
    assert snapshot.generation == 0
    assert [item.backend_value for item in snapshot.items] == [
        "cached/style.safetensors"
    ]
    assert snapshot.items[0].display_name == "Cached Style"
    assert snapshot.items[0].display_subtitle == "v1"
    assert snapshot.items[0].thumbnail_variants == (
        ModelThumbnailVariant(
            size=128,
            storage_key="ABC:128",
            width=85,
            height=128,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=65536,
        ),
    )


def test_model_catalog_refresh_snapshot_installs_canonical_generation(
    tmp_path: Path,
) -> None:
    """Refresh snapshot should install canonical items and advance kind generation."""

    backend = _FakeBackend((_entry("loras", "models/lora-a.safetensors", "ABC"),))
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    first_snapshot = service.refresh_snapshot("loras")
    backend.entries = (_entry("loras", "models/lora-b.safetensors", "DEF"),)
    second_items = service.refresh_models("loras")
    second_snapshot = service.cached_snapshot("loras")

    assert first_snapshot.kind == "loras"
    assert first_snapshot.generation == 1
    assert [item.backend_value for item in first_snapshot.items] == [
        "models/lora-a.safetensors"
    ]
    assert second_snapshot is not None
    assert second_items == second_snapshot.items
    assert second_snapshot.generation == 2
    assert [item.backend_value for item in second_snapshot.items] == [
        "models/lora-b.safetensors"
    ]


def test_model_catalog_uses_live_loras_enriched_by_cache_when_backend_available(
    tmp_path: Path,
) -> None:
    """Comfy-visible LoRA rows remain authoritative when backend is available."""

    backend = _FakeBackend((_entry("loras", "live/lora.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                kind="loras",
                value="cached/lora.safetensors",
                sha256="ABC",
                model_name="Cached LoRA",
                version_name="v1",
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
        model_metadata_root=tmp_path,
    )

    items = service.list_models("loras")

    assert backend.list_model_calls == [(("loras",), False)]
    assert [item.backend_value for item in items] == ["live/lora.safetensors"]
    assert items[0].relative_path == "live/lora.safetensors"
    assert items[0].display_name == "Cached LoRA"
    assert items[0].display_subtitle == "v1"
    assert items[0].trained_words == ("trigger",)
    assert items[0].thumbnail_variants == (
        ModelThumbnailVariant(
            size=128,
            storage_key="ABC:128",
            width=85,
            height=128,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=65536,
        ),
    )


def test_model_catalog_refresh_reconciles_lora_cache_bootstrap_with_backend(
    tmp_path: Path,
) -> None:
    """LoRA refresh should replace cache-only rows with live backend values."""

    backend = _FakeBackend((_entry("loras", "live/lora.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                kind="loras",
                value="cached/lora.safetensors",
                sha256="ABC",
                model_name="Cached LoRA",
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
        model_metadata_root=tmp_path,
    )

    initial_snapshot = service.snapshot_for_kind("loras")
    refreshed_snapshot = service.refresh_snapshot("loras")

    assert [item.backend_value for item in initial_snapshot.items] == [
        "live/lora.safetensors"
    ]
    assert backend.list_model_calls == [(("loras",), False), (("loras",), True)]
    assert refreshed_snapshot.generation == 1
    assert [item.backend_value for item in refreshed_snapshot.items] == [
        "live/lora.safetensors"
    ]
    assert refreshed_snapshot.items[0].display_name == "Cached LoRA"


def test_model_catalog_refresh_shows_empty_loras_when_backend_returns_empty(
    tmp_path: Path,
) -> None:
    """Backend emptiness should beat stale persisted LoRA metadata."""

    backend = _FakeBackend(())
    catalog = _FakeCatalog(
        (
            _record(
                kind="loras",
                value="cached/lora.safetensors",
                sha256="ABC",
                model_name="Cached LoRA",
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
        model_metadata_root=tmp_path,
    )

    snapshot = service.refresh_snapshot("loras")

    assert backend.list_model_calls == [(("loras",), True)]
    assert snapshot.generation == 1
    assert snapshot.items == ()


def test_model_catalog_loads_durable_snapshot_without_backend(
    tmp_path: Path,
) -> None:
    """A fresh catalog should restore the last authoritative snapshot locally."""

    snapshot_store = SqliteModelCatalogSnapshotStore(tmp_path)
    backend = _FakeBackend((_entry("loras", "models/lora.safetensors", "ABC"),))
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
        snapshot_store=snapshot_store,
    )
    saved_snapshot = service.refresh_snapshot("loras")
    fresh_backend = _FakeBackend(())
    fresh_service = ModelCatalogService(
        backend=fresh_backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
        snapshot_store=SqliteModelCatalogSnapshotStore(tmp_path),
    )

    loaded_snapshot = fresh_service.load_durable_snapshot("loras")

    assert loaded_snapshot is not None
    assert loaded_snapshot.kind == "loras"
    assert loaded_snapshot.generation == saved_snapshot.generation
    assert [item.backend_value for item in loaded_snapshot.items] == [
        "models/lora.safetensors"
    ]
    assert loaded_snapshot.items[0].size_bytes == 123
    assert loaded_snapshot.items[0].modified_at == "2026-04-14T01:00:00Z"
    assert fresh_backend.list_model_calls == []


def test_model_catalog_invalidate_clears_snapshot_and_advances_generation(
    tmp_path: Path,
) -> None:
    """Invalidation should make derived generation-sensitive caches stale."""

    backend = _FakeBackend((_entry("loras", "models/lora.safetensors", "ABC"),))
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    initial_snapshot = service.snapshot_for_kind("loras")
    service.invalidate("loras")
    reloaded_snapshot = service.snapshot_for_kind("loras")

    assert initial_snapshot.generation == 0
    assert service.cached_snapshot("loras") == reloaded_snapshot
    assert reloaded_snapshot.generation == 1
    assert backend.list_model_calls == [(("loras",), False), (("loras",), False)]


def test_model_catalog_merges_cached_metadata_by_sha256(tmp_path: Path) -> None:
    """SHA256 evidence should bind cached provider rows before local path keys."""

    backend = _FakeBackend(
        (
            _entry(
                "checkpoints",
                "real/final.safetensors",
                "ABC",
                display_name="final",
                sidecar_base_model="LocalBase",
            ),
        )
    )
    catalog = _FakeCatalog(
        (
            _record(
                kind="checkpoints",
                value="old/location.safetensors",
                sha256="ABC",
                model_name="Provider Checkpoint",
                version_name="v2.0",
                base_model="ProviderBase",
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
        model_metadata_root=tmp_path,
    )

    item = service.list_models("checkpoints")[0]

    assert item.display_name == "Provider Checkpoint"
    assert item.display_subtitle == "v2.0"
    assert item.backend_value == "real/final.safetensors"
    assert item.relative_path == "real/final.safetensors"
    assert item.folder == "real"
    assert item.basename == "final"
    assert item.extension == ".safetensors"
    assert item.base_model == "ProviderBase"
    assert item.trained_words == ("trigger",)
    assert item.tags == ("tag",)
    assert item.model_page_url == "https://civitai.com/models/1?modelVersionId=2"
    assert item.provider_name == "civitai"
    assert item.provider_model_id == "1"
    assert item.provider_model_version_id == "2"
    assert item.provider_model_name == "Provider Checkpoint"
    assert item.provider_model_version_name == "v2.0"
    assert "provider checkpoint" in item.search_text
    assert "real/final.safetensors" in item.search_text
    assert "providerbase" in item.search_text


def test_model_catalog_falls_back_to_kind_value_and_relative_path(
    tmp_path: Path,
) -> None:
    """Local evidence keys should match metadata when SHA256 evidence is unavailable."""

    backend = _FakeBackend(
        (
            _entry(
                "checkpoints",
                r"nested\model.ckpt",
                None,
                sidecar_base_model="SidecarBase",
            ),
        )
    )
    catalog = _FakeCatalog(
        (
            _record(
                kind="checkpoints",
                value=r"nested\model.ckpt",
                sha256="RECORDED",
                model_name="Matched by Path",
                version_name="Matched by Path",
                base_model=None,
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
        model_metadata_root=tmp_path,
    )

    item = service.list_models("checkpoints")[0]

    assert item.display_name == "Matched by Path"
    assert item.display_subtitle is None
    assert item.base_model == "SidecarBase"
    assert item.folder == "nested"
    assert item.basename == "model"
    assert item.collision_key == "model"


def test_model_catalog_preserves_thumbnail_variants_without_file_checks(
    tmp_path: Path,
) -> None:
    """Thumbnail storage references should pass through all roles deterministically."""

    backend = _FakeBackend((_entry("checkpoints", "model.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                kind="checkpoints",
                value="model.safetensors",
                sha256="ABC",
                model_name="Model",
                variants=(
                    ThumbnailVariant(
                        size=768,
                        storage_key="model:banner",
                        width=768,
                        height=160,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=491520,
                        role=BANNER_THUMBNAIL_ROLE,
                    ),
                    ThumbnailVariant(
                        size=128,
                        storage_key="model:standard",
                        width=85,
                        height=128,
                        content_format="sqthumb-qimage-argb32-premultiplied",
                        byte_size=43520,
                        role=STANDARD_THUMBNAIL_ROLE,
                    ),
                ),
            ),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=catalog,
        model_metadata_root=tmp_path,
    )

    item = service.list_models("checkpoints")[0]

    assert item.thumbnail_variants == (
        ModelThumbnailVariant(
            size=768,
            storage_key="model:banner",
            width=768,
            height=160,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=491520,
            role=BANNER_THUMBNAIL_ROLE,
        ),
        ModelThumbnailVariant(
            size=128,
            storage_key="model:standard",
            width=85,
            height=128,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=43520,
            role=STANDARD_THUMBNAIL_ROLE,
        ),
    )


def test_model_catalog_sorts_and_flags_basename_collisions(tmp_path: Path) -> None:
    """Catalog output should be deterministic and report duplicate bare names."""

    backend = _FakeBackend(
        (
            _entry("checkpoints", "z/model.safetensors", "AAA", display_name="Zulu"),
            _entry("checkpoints", "a/model.safetensors", "BBB", display_name="Alpha"),
            _entry("checkpoints", "m/other.safetensors", "CCC", display_name="Middle"),
        )
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    items = service.list_models("checkpoints")

    assert [item.display_name for item in items] == ["Alpha", "Middle", "Zulu"]
    model_items = [item for item in items if item.basename == "model"]
    assert len(model_items) == 2
    assert all(item.has_collision for item in model_items)
    assert all(item.collision_count == 2 for item in model_items)


def test_model_catalog_keeps_lora_prompt_rules_out_of_generic_rows(
    tmp_path: Path,
) -> None:
    """Generic rows should preserve backend values without LoRA prompt-name policy."""

    backend = _FakeBackend(
        (_entry("loras", "folder/token.safetensors", "ABC", display_name="token"),)
    )
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    item = service.list_models("loras")[0]

    assert item.backend_value == "folder/token.safetensors"
    assert not hasattr(item, "prompt_name")


def _entry(
    kind: str,
    value: str,
    sha256: str | None,
    *,
    display_name: str | None = None,
    sidecar_base_model: str | None = None,
) -> BackendModelCatalogEntry:
    """Return one backend model catalog entry."""

    suffix = Path(value.replace("\\", "/")).suffix or ".safetensors"
    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target-{kind}-{sha256 or value}",
        kind=kind,
        value=value,
        display_name=display_name if display_name is not None else Path(value).stem,
        source=BackendModelSource(root_id="root", relative_path=value),
        file=BackendModelFile(
            extension=suffix,
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.READY if sha256 else FingerprintStatus.MISSING,
            sha256=sha256,
            source="backend" if sha256 else None,
            computed_at="2026-04-14T01:00:00Z" if sha256 else None,
            error=None,
        ),
        sidecar=BackendSidecar(
            found=sidecar_base_model is not None,
            model_id=None,
            model_version_id=None,
            sha256=None,
            activation_text=None,
            description=None,
            base_model=sidecar_base_model,
            modified_at=None,
        ),
        local_preview=BackendLocalPreview(
            available=False,
            preview_id=None,
            url=None,
            source=None,
            modified_at=None,
            width=None,
            height=None,
        ),
    )


def _record(
    *,
    kind: str,
    value: str,
    sha256: str,
    model_name: str,
    version_name: str = "Version",
    base_model: str | None = "Base",
    variants: tuple[ThumbnailVariant, ...] | None = None,
) -> ModelMetadataCacheRecord:
    """Return one cached CivitAI metadata record."""

    resolved_variants = variants
    if resolved_variants is None:
        resolved_variants = (
            ThumbnailVariant(
                size=128,
                storage_key=f"{sha256}:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=65536,
            ),
        )
    return ModelMetadataCacheRecord(
        schema_version=1,
        local=LocalModelEvidence(
            target_id=f"target-{sha256}",
            root_id="root",
            relative_path=value,
            kind=kind,
            value=value,
            display_name=Path(value.replace("\\", "/")).stem,
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            sha256=sha256,
        ),
        provider=CivitaiModelVersion(
            model_id=1,
            model_version_id=2,
            model_name=model_name,
            model_type="Checkpoint",
            version_name=version_name,
            base_model=base_model,
            trained_words=("trigger",),
            description=None,
            version_description=None,
            tags=("tag",),
            creator_username=None,
            creator_image=None,
            nsfw=False,
            nsfw_level="None",
            availability=None,
            files=(),
            images=(),
            stats={},
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
            source_url="https://civitai.example/model",
            fetched_at="2026-04-14T12:00:00Z",
            raw_provider_payload={},
        ),
        provider_status="found",
        thumbnail=ThumbnailStoreResult(
            source="civitai",
            selection_policy="first-sfw-version-image",
            source_image_url="https://image.example/image.jpg",
            source_image_id=1,
            nsfw=False,
            nsfw_level="None",
            source_width=512,
            source_height=768,
            variants=resolved_variants,
            downloaded_at="2026-04-14T12:00:00Z",
        ),
        thumbnail_status=ThumbnailSelectionStatus.SELECTED,
        updated_at="2026-04-14T12:00:00Z",
    )
