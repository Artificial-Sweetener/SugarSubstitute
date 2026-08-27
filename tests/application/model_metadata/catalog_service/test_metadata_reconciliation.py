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

"""Test model-catalog metadata reconciliation behavior."""

from __future__ import annotations

from pathlib import Path

from substitute.application.model_metadata import (
    ModelCatalogService,
    ModelThumbnailVariant,
)

from .support import _FakeBackend, _FakeCatalog, _entry, _record


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
    )

    snapshot = service.refresh_snapshot("loras")

    assert backend.list_model_calls == [(("loras",), True)]
    assert snapshot.generation == 1
    assert snapshot.items == ()


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
    )

    item = service.list_models("checkpoints")[0]

    assert item.display_name == "Matched by Path"
    assert item.display_subtitle is None
    assert item.base_model == "SidecarBase"
    assert item.folder == "nested"
    assert item.basename == "model"
    assert item.collision_key == "model"


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
    )

    item = service.list_models("loras")[0]

    assert item.backend_value == "folder/token.safetensors"
    assert not hasattr(item, "prompt_name")
