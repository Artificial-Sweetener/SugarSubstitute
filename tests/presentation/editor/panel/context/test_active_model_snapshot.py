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

"""Test cached active-model snapshot resolution for an editor panel."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.presentation.editor.catalog.snapshots import CatalogSnapshotReadiness
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    CachedModelCatalogLookup,
    PanelActiveModelSnapshotController,
)


class CacheOnlyCatalogDouble(CachedModelCatalogLookup):
    """Provide deterministic in-memory and durable catalog snapshots."""

    def __init__(
        self,
        items_by_kind: dict[str, tuple[ModelCatalogItem, ...]],
        *,
        fail: bool = False,
        cold: bool = False,
        durable_items_by_kind: dict[str, tuple[ModelCatalogItem, ...]] | None = None,
    ) -> None:
        """Store cache state without allowing a foreground catalog request."""

        self._items_by_kind = items_by_kind
        self._fail = fail
        self._cold = cold
        self._durable_items_by_kind = durable_items_by_kind or {}
        self.requested_kinds: list[str] = []
        self.durable_requests: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Reject foreground model listing from the cache-only boundary."""

        raise AssertionError(f"unexpected foreground model listing for {kind}")

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured rows for protocol completeness."""

        return self._items_by_kind.get(kind, ())

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return the immediately available cached snapshot."""

        return self.cached_snapshot(kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return cached rows or the configured read failure."""

        self.requested_kinds.append(kind)
        if self._fail:
            raise RuntimeError("model catalog unavailable")
        if self._cold:
            return None
        return ModelCatalogSnapshot(
            kind=kind,
            items=self._items_by_kind.get(kind, ()),
            generation=7,
        )

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return legacy cached rows when in-memory snapshots are warm."""

        if self._cold:
            return None
        return self._items_by_kind.get(kind, ())

    def load_durable_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a durable snapshot without accessing a backend."""

        self.durable_requests.append(kind)
        rows = self._durable_items_by_kind.get(kind)
        if rows is None:
            return None
        return ModelCatalogSnapshot(kind=kind, items=rows, generation=11)

    def cached_metadata_snapshot_for_kind(
        self,
        kind: str,
    ) -> ModelCatalogSnapshot | None:
        """Provide no metadata fallback for deterministic cold-state coverage."""

        _ = kind
        return None

    def invalidate(self, kind: str | None = None) -> None:
        """Accept protocol invalidation without changing configured state."""

        _ = kind


def test_snapshot_resolves_diffusion_model_from_its_catalog_kind() -> None:
    """Resolve a standalone diffusion model from its own cached catalog kind."""

    item = _model_item(
        "diffusion_models",
        "Anima/hassakuAnima_v11.safetensors",
        "Hassaku Anima V11",
    )
    context = _active_context(
        node_type="SimpleSyrup.SimpleLoadAnima",
        field_key="diffusion_model",
        value="Anima\\hassakuAnima_v11.safetensors",
    )
    catalog = CacheOnlyCatalogDouble({"diffusion_models": (item,)})

    snapshot = PanelActiveModelSnapshotController(
        model_context=context,
        model_catalog_service=catalog,
    ).refresh_from_cache()

    assert snapshot.catalog_item is item
    assert snapshot.model_kind == "diffusion_models"
    assert snapshot.status.readiness is CatalogSnapshotReadiness.WARM
    assert catalog.requested_kinds == ["diffusion_models"]


def test_snapshot_resolves_diffusion_model_from_durable_catalog_when_memory_is_cold() -> (
    None
):
    """Read the authoritative durable snapshot when memory is cold."""

    item = _model_item(
        "diffusion_models",
        "Anima/hassakuAnima_v11.safetensors",
        "Hassaku (Anima)",
    )
    context = _active_context(
        node_type="SimpleSyrup.SimpleLoadAnima",
        field_key="diffusion_model",
        value="Anima\\hassakuAnima_v11.safetensors",
    )
    catalog = CacheOnlyCatalogDouble(
        {},
        cold=True,
        durable_items_by_kind={"diffusion_models": (item,)},
    )

    snapshot = PanelActiveModelSnapshotController(
        model_context=context,
        model_catalog_service=catalog,
    ).refresh_from_cache()

    assert snapshot.catalog_item is item
    assert snapshot.status.readiness is CatalogSnapshotReadiness.WARM
    assert catalog.durable_requests == ["diffusion_models"]


def test_snapshot_keeps_global_consumers_available_without_active_model() -> None:
    """Publish unavailable state without inventing model metadata."""

    snapshot = PanelActiveModelSnapshotController(
        model_context=PanelActiveModelContextController(),
        model_catalog_service=CacheOnlyCatalogDouble({}),
    ).refresh_from_cache()

    assert snapshot.model_value is None
    assert snapshot.catalog_item is None
    assert snapshot.status.readiness is CatalogSnapshotReadiness.UNAVAILABLE
    assert snapshot.identity.unavailable_reason == "active_model_unavailable"


def test_snapshot_reports_cold_and_failed_catalog_state_without_listing() -> None:
    """Fail closed for cold and failed cache reads while retaining identity."""

    context = _active_context(
        node_type="CheckpointLoaderSimple",
        field_key="ckpt_name",
        value="illustrious.safetensors",
    )
    cold = PanelActiveModelSnapshotController(
        model_context=context,
        model_catalog_service=CacheOnlyCatalogDouble({}, cold=True),
    ).refresh_from_cache()
    failed = PanelActiveModelSnapshotController(
        model_context=context,
        model_catalog_service=CacheOnlyCatalogDouble({}, fail=True),
    ).refresh_from_cache()

    assert cold.status.readiness is CatalogSnapshotReadiness.COLD
    assert cold.identity.unavailable_reason == "model_catalog_cold"
    assert failed.status.readiness is CatalogSnapshotReadiness.REFRESH_FAILED
    assert failed.identity.unavailable_reason == "model_catalog_unavailable"


def _active_context(
    *,
    node_type: str,
    field_key: str,
    value: str,
) -> PanelActiveModelContextController:
    """Build a context containing one generative-model candidate."""

    context = PanelActiveModelContextController()
    context.begin_projection(("Base",))
    context.record_node_inputs(
        cube_alias="Base",
        node_name="model",
        node_type=node_type,
        inputs={field_key: value},
    )
    return context


def _model_item(kind: str, backend_value: str, display_name: str) -> ModelCatalogItem:
    """Build one deterministic catalog item for snapshot contracts."""

    basename = backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors")
    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=None,
        backend_value=backend_value,
        relative_path=backend_value,
        folder="models",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=display_name.casefold(),
    )
