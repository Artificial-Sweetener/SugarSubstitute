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

"""Test model-catalog snapshot lifecycle behavior."""

from __future__ import annotations

from pathlib import Path
from threading import Event, Thread

from substitute.application.model_metadata import (
    ModelCatalogService,
    ModelCatalogSnapshot,
)
from substitute.domain.model_metadata import BackendModelCatalogEntry
from substitute.infrastructure.persistence import SqliteModelCatalogSnapshotStore

from .support import _FakeBackend, _FakeCatalog, _entry


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


def test_model_catalog_refresh_snapshot_installs_canonical_generation(
    tmp_path: Path,
) -> None:
    """Refresh snapshot should install canonical items and advance kind generation."""

    backend = _FakeBackend((_entry("loras", "models/lora-a.safetensors", "ABC"),))
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
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


def test_model_catalog_loads_durable_snapshot_without_backend(
    tmp_path: Path,
) -> None:
    """A fresh catalog should restore the last authoritative snapshot locally."""

    snapshot_store = SqliteModelCatalogSnapshotStore(tmp_path)
    backend = _FakeBackend((_entry("loras", "models/lora.safetensors", "ABC"),))
    service = ModelCatalogService(
        backend=backend,
        metadata_catalog=_FakeCatalog(()),
        snapshot_store=snapshot_store,
    )
    saved_snapshot = service.refresh_snapshot("loras")
    fresh_backend = _FakeBackend(())
    fresh_service = ModelCatalogService(
        backend=fresh_backend,
        metadata_catalog=_FakeCatalog(()),
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
    )

    initial_snapshot = service.snapshot_for_kind("loras")
    service.invalidate("loras")
    reloaded_snapshot = service.snapshot_for_kind("loras")

    assert initial_snapshot.generation == 0
    assert service.cached_snapshot("loras") == reloaded_snapshot
    assert reloaded_snapshot.generation == 1
    assert backend.list_model_calls == [(("loras",), False), (("loras",), False)]
