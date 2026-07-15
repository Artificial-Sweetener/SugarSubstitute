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

"""Tests for prompt-editor LoRA catalog projection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from substitute.application.model_metadata import ModelCatalogService
from substitute.application.prompt_editor import (
    PromptLoraCatalogService,
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.prompt_lora_catalog_service import (
    _find_lora_in_snapshot,
)
from substitute.application.prompt_editor.prompt_lora_diagnostics import (
    lora_prompt_context,
    lora_source_range_context,
)
from substitute.domain.model_metadata import (
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
    ThumbnailSelectionStatus,
    ThumbnailStoreResult,
    ThumbnailVariant,
)


class _FakeBackend:
    """Return deterministic backend model catalog entries."""

    def __init__(
        self,
        entries: tuple[BackendModelCatalogEntry, ...],
        *,
        fail_refresh: bool = False,
    ) -> None:
        """Store fake entries for assertions."""

        self.entries = entries
        self.fail_refresh = fail_refresh
        self.list_model_calls = 0
        self.list_model_refreshes: list[bool] = []

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
        """Return fake model entries for the requested LoRA kind."""

        assert kinds == ("loras",)
        self.list_model_calls += 1
        self.list_model_refreshes.append(refresh)
        if refresh and self.fail_refresh:
            raise RuntimeError("Backend model catalog refresh failed.")
        return self.entries


class _FakeCatalog:
    """Return deterministic cached metadata records."""

    def __init__(self, records: tuple[ModelMetadataCacheRecord, ...]) -> None:
        """Store fake metadata records for assertions."""

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


def test_lora_catalog_inserts_relative_prompt_names_and_tracks_collisions(
    tmp_path: Path,
) -> None:
    """Catalog items should preserve backend path style and flag bare-name collisions."""

    backend = _FakeBackend(
        (
            _entry("Pony\\Concept\\Expressive_H-000001.safetensors", "ABC"),
            _entry("Pony\\Style\\Expressive_H-000001.safetensors", "DEF"),
            _entry("Illustrious/Character/Mineru.safetensors", "GHI"),
        )
    )
    catalog = _FakeCatalog(
        (
            _record(
                value="Pony\\Concept\\Expressive_H-000001.safetensors",
                sha256="ABC",
                model_name="Expressive_H-000001",
                version_name="",
            ),
            _record(
                value="Pony\\Style\\Expressive_H-000001.safetensors",
                sha256="DEF",
                model_name="Expressive_H-000001",
                version_name="",
            ),
            _record(
                value="Illustrious/Character/Mineru.safetensors",
                sha256="GHI",
                model_name="Mineru",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog, model_metadata_root=tmp_path)

    items = service.list_loras()

    mineru = next(item for item in items if item.display_name == "Mineru")
    assert mineru.prompt_name == "Illustrious/Character/Mineru"
    assert mineru.thumbnail_variants == (
        PromptLoraThumbnailVariant(
            size=128,
            storage_key="GHI:128",
            width=85,
            height=128,
            content_format="sqthumb-qimage-argb32-premultiplied",
            byte_size=65536,
        ),
    )
    assert "mineru" in mineru.search_text
    assert mineru.display_subtitle == "Version"
    assert mineru.model_page_url == "https://civitai.com/models/1?modelVersionId=2"
    assert mineru.has_collision is False

    collisions = [item for item in items if item.basename == "Expressive_H-000001"]
    assert len(collisions) == 2
    assert {item.prompt_name for item in collisions} == {
        "Pony\\Concept\\Expressive_H-000001",
        "Pony\\Style\\Expressive_H-000001",
    }
    assert all(item.has_collision for item in collisions)
    assert all(item.collision_count == 2 for item in collisions)
    assert all(item.display_subtitle is None for item in collisions)
    assert all(item.model_page_url is not None for item in collisions)
    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [False]

    assert service.list_loras() == items
    assert backend.list_model_calls == 1


def test_lora_catalog_cached_loras_is_non_loading_when_cold(
    tmp_path: Path,
) -> None:
    """Cached-only LoRA reads should not ask Backend when no snapshot is installed."""

    backend = _FakeBackend((_entry("models/available.safetensors", "ABC"),))
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    assert service.cached_loras() is None
    assert backend.list_model_calls == 0


def test_lora_catalog_cached_loras_returns_installed_snapshot(
    tmp_path: Path,
) -> None:
    """Cached-only LoRA reads should return installed prompt snapshots."""

    backend = _FakeBackend((_entry("models/available.safetensors", "ABC"),))
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    prompt_snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )
    service.install_snapshot(prompt_snapshot)
    backend.entries = (_entry("models/stale-if-loaded.safetensors", "DEF"),)

    cached = service.cached_loras()

    assert cached is not None
    assert [item.prompt_name for item in cached] == ["models/available"]
    assert backend.list_model_calls == 1


def test_lora_catalog_bootstraps_cached_metadata_without_backend(
    tmp_path: Path,
) -> None:
    """Persisted metadata should make known LoRAs render before Backend is ready."""

    backend = _FakeBackend(())
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(
            (
                _record(
                    value="cached/Style.safetensors",
                    sha256="ABC",
                    model_name="Cached Style",
                    storage_key="ABC:banner:768",
                ),
            )
        ),
        model_metadata_root=tmp_path,
    )

    cached = service.cached_loras()
    item = service.find_lora("cached/Style")

    assert backend.list_model_calls == 0
    assert cached is not None
    assert [row.prompt_name for row in cached] == ["cached/Style"]
    assert item is not None
    assert item.display_name == "Cached Style"
    assert item.thumbnail_variants[0].storage_key == "ABC:banner:768"
    assert service.can_report_lora_absence() is False


def test_lora_catalog_cold_find_lora_does_not_load_backend(
    tmp_path: Path,
) -> None:
    """Render-time lookup should not block on Backend when no cache is installed."""

    backend = _FakeBackend((_entry("models/available.safetensors", "ABC"),))
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    assert service.find_lora("models/available") is None
    assert service.can_report_lora_absence() is False
    assert backend.list_model_calls == 0


def test_lora_catalog_refresh_loras_uses_backend_refresh(
    tmp_path: Path,
) -> None:
    """Explicit picker refresh should ask Backend for fresh LoRA availability."""

    backend = _FakeBackend((_entry("models/available.safetensors", "ABC"),))
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    items = service.refresh_loras()

    assert [item.prompt_name for item in items] == ["models/available"]
    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [True]


def test_lora_catalog_keeps_storage_key_thumbnail_variants(
    tmp_path: Path,
) -> None:
    """Cached thumbnail storage keys should pass through without filesystem checks."""

    backend = _FakeBackend((_entry("models/lora.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                value="models/lora.safetensors",
                sha256="ABC",
                model_name="Lora",
                storage_key="ABC:128",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog, model_metadata_root=tmp_path)

    item = service.list_loras()[0]

    assert item.thumbnail_variants[0].storage_key == "ABC:128"


def test_lora_catalog_explicit_refresh_shows_empty_when_backend_returns_empty(
    tmp_path: Path,
) -> None:
    """Explicit Backend refresh should replace stale bootstrap LoRA metadata."""

    backend = _FakeBackend(())
    catalog = _FakeCatalog(
        (
            _record(
                value="cached/Cached.safetensors",
                sha256="ABC",
                model_name="Cached Prompt LoRA",
                storage_key="ABC:standard:128",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog, model_metadata_root=tmp_path)

    items = service.refresh_loras()

    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [True]
    assert items == ()
    assert service.find_lora("cached/Cached") is None
    assert service.can_report_lora_absence() is True


def test_lora_catalog_keeps_page_name_and_version_names(
    tmp_path: Path,
) -> None:
    """CivitAI page and version names should remain explicit catalog fields."""

    backend = _FakeBackend((_entry("sd15/GesuGao.safetensors", "ABC"),))
    catalog = _FakeCatalog(
        (
            _record(
                value="sd15/GesuGao.safetensors",
                sha256="ABC",
                model_name="Gesugao",
                version_name="v2.0",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog, model_metadata_root=tmp_path)

    item = service.list_loras()[0]

    assert item.display_name == "Gesugao"
    assert item.display_subtitle == "v2.0"


def test_lora_catalog_keeps_descriptive_version_name_as_subtitle(
    tmp_path: Path,
) -> None:
    """Hub-style CivitAI pages should keep their page and version labels separate."""

    backend = _FakeBackend(
        (_entry("Pony/Pose/battoujutsu_sword_stance.safetensors", "ABC"),)
    )
    catalog = _FakeCatalog(
        (
            _record(
                value="Pony/Pose/battoujutsu_sword_stance.safetensors",
                sha256="ABC",
                model_name="Sword stances collection [Pony]",
                version_name="Battoujutsu",
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog, model_metadata_root=tmp_path)

    item = service.list_loras()[0]

    assert item.display_name == "Sword stances collection [Pony]"
    assert item.display_subtitle == "Battoujutsu"
    assert "sword stances" in item.search_text
    assert "battoujutsu" in item.search_text


def test_lora_catalog_keeps_duplicate_page_names_with_version_subtitles(
    tmp_path: Path,
) -> None:
    """Duplicate page names should keep provider version subtitles unchanged."""

    backend = _FakeBackend(
        (
            _entry("SD 1.5/GesuGao.safetensors", "ABC"),
            _entry("SD 1.5/edgGesugao.safetensors", "DEF"),
        )
    )
    catalog = _FakeCatalog(
        (
            _record(
                value="SD 1.5/GesuGao.safetensors",
                sha256="ABC",
                model_name="Gesugao",
                version_name="v1.0",
                model_version_id=1,
            ),
            _record(
                value="SD 1.5/edgGesugao.safetensors",
                sha256="DEF",
                model_name="Gesugao",
                version_name="v2.0",
                model_version_id=2,
            ),
        )
    )
    service = _service(backend=backend, catalog=catalog, model_metadata_root=tmp_path)

    items = service.list_loras()

    assert {item.display_name for item in items} == {"Gesugao"}
    assert {item.display_subtitle for item in items} == {"v1.0", "v2.0"}
    assert all("gesugao" in item.search_text for item in items)
    assert any("v1.0" in item.search_text for item in items)
    assert any("v2.0" in item.search_text for item in items)


def test_lora_catalog_resolves_unique_bare_prompt_name_to_nested_item(
    tmp_path: Path,
) -> None:
    """Pasted bare LoRA names should resolve after the catalog is passively loaded."""

    backend = _FakeBackend(
        (
            _entry(
                r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1.safetensors",
                "ABC",
            ),
        )
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    service.list_loras()
    item = service.find_lora("Ranni_illusXLNoobAI_Incrs_v1")

    assert item is not None
    assert item.prompt_name == r"illustrious\characters\Ranni_illusXLNoobAI_Incrs_v1"


def test_lora_catalog_repairs_stale_prompt_path_by_unique_basename(
    tmp_path: Path,
) -> None:
    """Wrong restored LoRA folders should repair when the basename is unique."""

    backend = _FakeBackend(
        (_entry(r"NoobAI\Bridge Tools Line Weight.safetensors", "ABC"),)
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    service.list_loras()
    diagnostic = service.lookup_lora(r"ILLUSTRIOUS\CONCEPTS\Bridge Tools Line Weight")

    assert diagnostic.match_source == "autocomplete_ranked_basename"
    assert diagnostic.result is not None
    assert diagnostic.result.backend_value == (
        r"NoobAI\Bridge Tools Line Weight.safetensors"
    )


def test_lora_catalog_find_lora_does_not_require_backend_refresh(
    tmp_path: Path,
) -> None:
    """Loaded LoRA lookup should not require a fresh Backend refresh."""

    backend = _FakeBackend(
        (_entry(r"illustrious\characters\Ranni.safetensors", "ABC"),),
        fail_refresh=True,
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    service.list_loras()
    item = service.find_lora("Ranni")

    assert item is not None
    assert item.prompt_name == r"illustrious\characters\Ranni"
    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [False]


def test_lora_catalog_uses_first_ranked_duplicate_bare_prompt_name(
    tmp_path: Path,
) -> None:
    """Duplicate pasted bare LoRA names should pick autocomplete's first candidate."""

    backend = _FakeBackend(
        (
            _entry(r"z-last\characters\Ranni.safetensors", "ABC"),
            _entry(r"a-first\characters\Ranni.safetensors", "DEF"),
        )
    )
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    service.list_loras()
    diagnostic = service.lookup_lora("Ranni")

    assert diagnostic.match_source == "autocomplete_ranked_exact"
    assert diagnostic.fallback_candidate_count == 2
    assert diagnostic.selected_fallback_rank == 0
    assert diagnostic.result is not None
    assert diagnostic.result.backend_value == r"a-first\characters\Ranni.safetensors"
    assert service.find_lora(r"z-last\characters\Ranni") is not None


def test_lora_catalog_installs_prepared_snapshot_and_advances_revision(
    tmp_path: Path,
) -> None:
    """Prepared snapshots should install atomically without caller-side adaptation."""

    backend = _FakeBackend((_entry("first.safetensors", "ABC"),))
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    initial_revision = service.cache_revision
    model_snapshot = model_catalog.refresh_snapshot("loras")
    snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )
    backend.entries = (_entry("second.safetensors", "DEF"),)

    service.install_snapshot(snapshot)

    assert snapshot.model_generation == 1
    assert service.cache_revision == initial_revision + 1
    assert [item.prompt_name for item in service.list_loras()] == ["first"]
    assert service.find_lora("first") is not None
    assert service.find_lora("second") is None


def test_lora_catalog_prepares_snapshot_from_canonical_model_generation(
    tmp_path: Path,
) -> None:
    """Prompt LoRA snapshots should derive directly from canonical model rows."""

    backend = _FakeBackend((_entry("models/midna.safetensors", "ABC"),))
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(
            (
                _record(
                    value="models/midna.safetensors",
                    sha256="ABC",
                    model_name="Midna",
                    storage_key="ABC:banner:768",
                ),
            )
        ),
        model_metadata_root=tmp_path,
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)

    prompt_snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )
    service.install_snapshot(prompt_snapshot)

    item = service.find_lora("models/midna")
    assert prompt_snapshot.model_generation == model_snapshot.generation
    assert service.cache_revision == 1
    assert item is not None
    assert item.display_name == "Midna"
    assert item.thumbnail_variants[0].storage_key == "ABC:banner:768"


def test_lora_catalog_reinstalling_same_generation_keeps_revision(
    tmp_path: Path,
) -> None:
    """Installing identical derived prompt snapshots should avoid cache churn."""

    backend = _FakeBackend((_entry("models/midna.safetensors", "ABC"),))
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    prompt_snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )

    service.install_snapshot(prompt_snapshot)
    first_revision = service.cache_revision
    service.install_snapshot(prompt_snapshot)

    assert service.cache_revision == first_revision


def test_lora_catalog_invalidate_preserves_authoritative_snapshot(
    tmp_path: Path,
) -> None:
    """Backend event invalidation should not clear last-known authoritative LoRAs."""

    backend = _FakeBackend((_entry("models/midna.safetensors", "ABC"),))
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    service.refresh_loras()

    service.invalidate()

    assert service.can_report_lora_absence() is True
    assert service.find_lora("models/midna") is not None


def test_lora_catalog_uses_indexed_backend_value_matches(
    tmp_path: Path,
) -> None:
    """Indexed lookup should preserve extension and backend path matching behavior."""

    backend = _FakeBackend((_entry(r"folder\Character.safetensors", "ABC"),))
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )

    service.list_loras()

    assert service.find_lora(r"folder\Character") is not None
    assert service.find_lora(r"folder/Character.safetensors") is not None
    assert backend.list_model_calls == 1


def test_lora_diagnostic_context_normalizes_lookup_fields() -> None:
    """LoRA diagnostic context should expose safe prompt lookup keys."""

    context = lora_prompt_context(r"Folder\Character.safetensors")
    range_context = lora_source_range_context(4, 12)

    assert context == {
        "lora_prompt_name": r"Folder\Character.safetensors",
        "lora_prompt_name_length": len(r"Folder\Character.safetensors"),
        "lora_prompt_name_sha256_12": "e77f9ce2f058",
        "lora_prompt_lookup_key": "folder/character",
        "lora_backend_lookup_key": "folder/character.safetensors",
        "lora_has_path_separator": True,
    }
    assert range_context == {
        "lora_source_start": 4,
        "lora_source_end": 12,
        "lora_source_length": 8,
    }


def test_lora_lookup_diagnostic_reports_match_sources(tmp_path: Path) -> None:
    """LoRA lookup diagnostics should explain which index produced a match."""

    backend = _FakeBackend(
        (
            _entry(r"folder\Character.safetensors", "ABC"),
            _entry(r"other\Solo.safetensors", "DEF"),
        )
    )
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )
    backend_only_snapshot = replace(
        snapshot,
        prompt_name_items=MappingProxyType({}),
    )

    prompt_match = _find_lora_in_snapshot(snapshot, r"folder\Character")
    backend_match = _find_lora_in_snapshot(
        backend_only_snapshot,
        r"folder/Character.safetensors",
    )
    bare_match = _find_lora_in_snapshot(snapshot, "Solo")

    assert prompt_match.match_source == "prompt_name"
    assert prompt_match.result is not None
    assert backend_match.match_source == "backend_value"
    assert backend_match.result is not None
    assert bare_match.match_source == "autocomplete_ranked_exact"
    assert bare_match.bare_collision_match_count == 1
    assert bare_match.result is not None


def test_lora_lookup_diagnostic_reports_ranked_duplicate_selection(
    tmp_path: Path,
) -> None:
    """Duplicate bare LoRA names should report ranked fallback selection."""

    backend = _FakeBackend(
        (
            _entry(r"z-last\characters\Ranni.safetensors", "ABC"),
            _entry(r"a-first\characters\Ranni.safetensors", "DEF"),
        )
    )
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        model_metadata_root=tmp_path,
    )
    model_snapshot = model_catalog.refresh_snapshot("loras")
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    snapshot = service.prepare_snapshot_from_models(
        model_snapshot.items,
        model_generation=model_snapshot.generation,
    )

    diagnostic = _find_lora_in_snapshot(snapshot, "Ranni")

    assert diagnostic.match_source == "autocomplete_ranked_exact"
    assert diagnostic.bare_collision_match_count == 2
    assert diagnostic.fallback_candidate_count == 2
    assert diagnostic.selected_fallback_rank == 0
    assert diagnostic.result is not None
    assert diagnostic.result.backend_value == r"a-first\characters\Ranni.safetensors"


def _entry(value: str, sha256: str) -> BackendModelCatalogEntry:
    """Return one backend LoRA catalog entry."""

    return BackendModelCatalogEntry(
        schema_version=1,
        target_id=f"target-{sha256}",
        kind="loras",
        value=value,
        display_name=Path(value.replace("\\", "/")).stem,
        source=BackendModelSource(root_id="root", relative_path=value),
        file=BackendModelFile(
            extension=".safetensors",
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            created_at=None,
        ),
        fingerprint=BackendFingerprint(
            status=FingerprintStatus.READY,
            sha256=sha256,
            source="backend",
            computed_at="2026-04-14T01:00:00Z",
            error=None,
        ),
        sidecar=BackendSidecar(
            found=False,
            model_id=None,
            model_version_id=None,
            sha256=None,
            activation_text=None,
            description=None,
            base_model=None,
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


def _service(
    *,
    backend: _FakeBackend,
    catalog: _FakeCatalog,
    model_metadata_root: Path,
) -> PromptLoraCatalogService:
    """Return a LoRA catalog service using the shared generic model catalog."""

    return PromptLoraCatalogService(
        model_catalog=ModelCatalogService(
            backend=backend,
            metadata_catalog=catalog,
            model_metadata_root=model_metadata_root,
        )
    )


def _record(
    *,
    value: str,
    sha256: str,
    model_name: str,
    version_name: str = "Version",
    model_id: int = 1,
    model_version_id: int = 2,
    storage_key: str | None = None,
) -> ModelMetadataCacheRecord:
    """Return one cached CivitAI metadata record."""

    resolved_storage_key = storage_key if storage_key is not None else f"{sha256}:128"
    return ModelMetadataCacheRecord(
        schema_version=1,
        local=LocalModelEvidence(
            target_id=f"target-{sha256}",
            root_id="root",
            relative_path=value,
            kind="loras",
            value=value,
            display_name=Path(value.replace("\\", "/")).stem,
            size_bytes=123,
            modified_at="2026-04-14T01:00:00Z",
            sha256=sha256,
        ),
        provider=CivitaiModelVersion(
            model_id=model_id,
            model_version_id=model_version_id,
            model_name=model_name,
            model_type="LORA",
            version_name=version_name,
            base_model="Illustrious",
            trained_words=("mineru",),
            description=None,
            version_description=None,
            tags=("character",),
            creator_username=None,
            creator_image=None,
            nsfw=False,
            nsfw_level="None",
            availability=None,
            files=(),
            images=(),
            stats={},
            model_page_url=(
                f"https://civitai.com/models/{model_id}"
                f"?modelVersionId={model_version_id}"
            ),
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
            variants=(
                ThumbnailVariant(
                    size=128,
                    storage_key=resolved_storage_key,
                    width=85,
                    height=128,
                    content_format="sqthumb-qimage-argb32-premultiplied",
                    byte_size=65536,
                ),
            ),
            downloaded_at="2026-04-14T12:00:00Z",
        ),
        thumbnail_status=ThumbnailSelectionStatus.SELECTED,
        updated_at="2026-04-14T12:00:00Z",
    )
