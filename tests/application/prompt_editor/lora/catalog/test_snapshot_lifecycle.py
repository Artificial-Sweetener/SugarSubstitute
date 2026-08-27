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

"""Prompt LoRA catalog lifecycle contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.application.model_metadata import ModelCatalogService
from substitute.application.prompt_editor.lora.catalog import PromptLoraCatalogService

from tests.application.prompt_editor.lora.catalog.support import (
    _FakeBackend,
    _FakeCatalog,
    _entry,
    _record,
    _service,
)


def test_lora_catalog_cached_loras_is_non_loading_when_cold(
    tmp_path: Path,
) -> None:
    """Cached-only LoRA reads should not ask Backend when no snapshot is installed."""

    backend = _FakeBackend((_entry("models/available.safetensors", "ABC"),))
    service = _service(
        backend=backend,
        catalog=_FakeCatalog(()),
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
    )

    items = service.refresh_loras()

    assert [item.prompt_name for item in items] == ["models/available"]
    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [True]


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
    service = _service(backend=backend, catalog=catalog)

    items = service.refresh_loras()

    assert backend.list_model_calls == 1
    assert backend.list_model_refreshes == [True]
    assert items == ()
    assert service.find_lora("cached/Cached") is None
    assert service.can_report_lora_absence() is True


def test_lora_catalog_installs_prepared_snapshot_and_advances_revision(
    tmp_path: Path,
) -> None:
    """Prepared snapshots should install atomically without caller-side adaptation."""

    backend = _FakeBackend((_entry("first.safetensors", "ABC"),))
    model_catalog = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
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
    )
    service = PromptLoraCatalogService(model_catalog=model_catalog)
    service.refresh_loras()

    service.invalidate()

    assert service.can_report_lora_absence() is True
    assert service.find_lora("models/midna") is not None
