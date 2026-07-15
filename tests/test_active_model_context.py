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

"""Tests for active generative-model context and cached catalog resolution."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.presentation.editor.catalog.snapshots import CatalogSnapshotReadiness
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
    matching_catalog_item,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)


class _Catalog:
    """Return cached model rows by kind or raise a configured failure."""

    def __init__(
        self,
        items_by_kind: dict[str, tuple[ModelCatalogItem, ...]],
        *,
        fail: bool = False,
        cold: bool = False,
        durable_items_by_kind: dict[str, tuple[ModelCatalogItem, ...]] | None = None,
    ) -> None:
        """Store deterministic cache behavior."""

        self.items_by_kind = items_by_kind
        self.fail = fail
        self.cold = cold
        self.durable_items_by_kind = durable_items_by_kind or {}
        self.requested_kinds: list[str] = []
        self.durable_requests: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Fail if foreground context tries to list models."""

        raise AssertionError(f"unexpected foreground model listing for {kind}")

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return configured rows for protocol completeness."""

        return self.items_by_kind.get(kind, ())

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached model snapshot without loading rows."""

        return self.cached_snapshot(kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return cached rows for the requested model kind."""

        self.requested_kinds.append(kind)
        if self.fail:
            raise RuntimeError("model catalog unavailable")
        if self.cold:
            return None
        return ModelCatalogSnapshot(
            kind=kind,
            items=self.items_by_kind.get(kind, ()),
            generation=7,
        )

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return legacy cached rows only when available."""

        if self.cold:
            return None
        return self.items_by_kind.get(kind, ())

    def load_durable_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return configured durable rows without accessing a backend."""

        self.durable_requests.append(kind)
        rows = self.durable_items_by_kind.get(kind)
        if rows is None:
            return None
        return ModelCatalogSnapshot(kind=kind, items=rows, generation=11)

    def cached_metadata_snapshot_for_kind(
        self,
        kind: str,
    ) -> ModelCatalogSnapshot | None:
        """Return no metadata fallback for deterministic cold-state coverage."""

        _ = kind
        return None

    def invalidate(self, kind: str | None = None) -> None:
        """Accept invalidation for protocol completeness."""

        _ = kind


def test_active_model_uses_stack_order_across_checkpoint_and_diffusion_fields() -> None:
    """The first stack-ordered generative model should own panel context."""

    context = PanelActiveModelContextController()
    context.begin_projection(("First", "Later"))
    context.record_node_inputs(
        cube_alias="Later",
        node_name="checkpoint",
        node_type="CheckpointLoaderSimple",
        inputs={"ckpt_name": "later.safetensors"},
    )
    context.record_node_inputs(
        cube_alias="First",
        node_name="models",
        node_type="SimpleSyrup.SimpleLoadAnima",
        inputs={"diffusion_model": "Anima/first.safetensors"},
    )

    candidate = context.current_model()

    assert candidate is not None
    assert candidate.model_kind == "diffusion_models"
    assert candidate.value == "Anima/first.safetensors"


def test_active_model_field_update_supports_unet_and_removal() -> None:
    """Live diffusion-model changes should update and remove active context."""

    context = PanelActiveModelContextController()
    context.begin_projection(("Base",))

    assert context.update_field_value(
        cube_alias="Base",
        node_name="model",
        node_type="UNETLoader",
        field_key="unet_name",
        value="flux.safetensors",
    )
    assert context.current_model() is not None
    assert context.update_field_value(
        cube_alias="Base",
        node_name="model",
        node_type="UNETLoader",
        field_key="unet_name",
        value="",
    )
    assert context.current_model() is None


def test_active_model_cube_rename_preserves_candidate_precedence() -> None:
    """Renaming a cube should retain its active-model stack position."""

    context = PanelActiveModelContextController()
    context.begin_projection(("First", "Later"))
    context.record_node_inputs(
        cube_alias="First",
        node_name="model",
        node_type="UNETLoader",
        inputs={"unet_name": "first.safetensors"},
    )
    context.record_node_inputs(
        cube_alias="Later",
        node_name="model",
        node_type="UNETLoader",
        inputs={"unet_name": "later.safetensors"},
    )

    context.rename_cube("First", "Renamed")

    candidate = context.current_model()
    assert candidate is not None
    assert candidate.cube_alias == "Renamed"
    assert candidate.value == "first.safetensors"


def test_matching_catalog_item_supports_paths_basenames_and_stems() -> None:
    """Model matching should preserve flexible path and stem handling."""

    item = _model_item(
        "checkpoints",
        "models/checkpoints/illustrious.safetensors",
        "Illustrious",
    )

    assert (
        matching_catalog_item("models\\checkpoints\\illustrious.safetensors", (item,))
        is item
    )
    assert matching_catalog_item("illustrious.safetensors", (item,)) is item
    assert matching_catalog_item("illustrious", (item,)) is item


def test_snapshot_resolves_diffusion_model_from_its_catalog_kind() -> None:
    """Standalone diffusion models should resolve from diffusion_models cache."""

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
    catalog = _Catalog({"diffusion_models": (item,)})

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
    """Cold-start preset context should consume the authoritative durable snapshot."""

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
    catalog = _Catalog(
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
    """Missing model context should be explicit without inventing model metadata."""

    snapshot = PanelActiveModelSnapshotController(
        model_context=PanelActiveModelContextController(),
        model_catalog_service=_Catalog({}),
    ).refresh_from_cache()

    assert snapshot.model_value is None
    assert snapshot.catalog_item is None
    assert snapshot.status.readiness is CatalogSnapshotReadiness.UNAVAILABLE
    assert snapshot.identity.unavailable_reason == "active_model_unavailable"


def test_snapshot_reports_cold_and_failed_catalog_state_without_listing() -> None:
    """Cache-only resolution should fail closed while preserving active identity."""

    context = _active_context(
        node_type="CheckpointLoaderSimple",
        field_key="ckpt_name",
        value="illustrious.safetensors",
    )
    cold = PanelActiveModelSnapshotController(
        model_context=context,
        model_catalog_service=_Catalog({}, cold=True),
    ).refresh_from_cache()
    failed = PanelActiveModelSnapshotController(
        model_context=context,
        model_catalog_service=_Catalog({}, fail=True),
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
    """Return one context containing a single generative-model candidate."""

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
    """Return one deterministic catalog item."""

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
