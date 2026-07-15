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

"""Contract tests for editor saved-dimension menu source composition."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
)
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
)
from substitute.presentation.editor.panel.menus.dimension_preset_menu_source import (
    EditorDimensionPresetMenuSource,
)
from substitute.presentation.editor.panel.menus.dimension_preset_models import (
    DimensionPresetMenuModel,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)


class _MemoryRepository:
    """Store user presets in memory for menu-source tests."""

    def __init__(self, presets: tuple[UserPreset, ...] = ()) -> None:
        """Initialize stored presets."""

        self.presets = presets

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return stored presets."""

        return self.presets

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Persist presets in memory."""

        self.presets = presets


class _Catalog:
    """Return cached test model catalog items by kind."""

    def __init__(
        self,
        items: tuple[ModelCatalogItem, ...],
        *,
        fail: bool = False,
    ) -> None:
        """Store checkpoint catalog items."""

        self.items = items
        self.fail = fail
        self.list_calls = 0

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Fail if menu model construction tries to list checkpoint models."""

        self.list_calls += 1
        raise AssertionError(f"unexpected foreground model listing for {kind}")

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return checkpoint models for refresh calls."""

        assert kind == "checkpoints"
        return self.items

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return cached checkpoint rows without loading the catalog."""

        return self.cached_snapshot(kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return cached checkpoint rows or fail like the catalog cache."""

        assert kind == "checkpoints"
        if self.fail:
            raise RuntimeError("checkpoint catalog unavailable")
        return ModelCatalogSnapshot(kind=kind, items=self.items, generation=3)

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached checkpoint rows for legacy cache readers."""

        assert kind == "checkpoints"
        if self.fail:
            raise RuntimeError("checkpoint catalog unavailable")
        return self.items

    def invalidate(self, kind: str | None = None) -> None:
        """Record no state for invalidation in tests."""

        _ = kind


def test_source_lists_family_and_global_dimension_sections() -> None:
    """The source should expose active-family presets before global presets."""

    illustrious = _family("illustrious", "Illustrious")
    repository = _MemoryRepository(
        (
            _preset(
                "dimension:global",
                short_edge=832,
                long_edge=1216,
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
            _preset(
                "dimension:family",
                short_edge=1024,
                long_edge=1536,
                associations=(illustrious,),
            ),
        )
    )
    source = _source(
        repository,
        panel=_panel_for_checkpoint("models/illustrious.safetensors"),
        catalog=(
            _model_item(
                backend_value="models/illustrious.safetensors",
                display_name="Illustrious XL",
                base_model="Illustrious",
            ),
        ),
    )

    model = _prepared_model(source)

    assert model.model_save_label == "Illustrious"
    assert [section.title for section in model.sections] == [
        "For Illustrious",
        "Global",
    ]
    assert [
        (item.short_edge, item.long_edge) for item in model.sections[0].presets
    ] == [(1024, 1536)]
    assert [
        (item.short_edge, item.long_edge) for item in model.sections[1].presets
    ] == [(832, 1216)]


def test_source_saves_current_dimensions_globally() -> None:
    """Global saves should write the canonical shape with the global association."""

    repository = _MemoryRepository()
    source = _source(repository, panel=_panel_for_checkpoint("missing.safetensors"))

    source.save_current_dimensions_globally(1536, 1024)

    assert len(repository.presets) == 1
    assert repository.presets[0].payload == DimensionPresetPayload(
        short_edge=1024,
        long_edge=1536,
    )
    assert repository.presets[0].associations == (GLOBAL_PRESET_ASSOCIATION,)


def test_source_saves_current_dimensions_for_active_model_family() -> None:
    """Model saves should use the active checkpoint's broad family association."""

    repository = _MemoryRepository()
    source = _source(
        repository,
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        catalog=(
            _model_item(
                backend_value="models/illustrious.safetensors",
                display_name="Illustrious XL",
                base_model="Illustrious",
            ),
        ),
    )

    source.prepare_dimension_preset_menu_model(reason="test")
    source.save_current_dimensions_for_model(1536, 1024)

    assert len(repository.presets) == 1
    assert repository.presets[0].associations == (
        _family("illustrious", "Illustrious"),
    )


def test_source_omits_model_save_label_when_checkpoint_has_no_family() -> None:
    """Unknown checkpoint metadata should leave only global preset support."""

    repository = _MemoryRepository()
    source = _source(
        repository,
        panel=_panel_for_checkpoint("unknown.safetensors"),
        catalog=(
            _model_item(
                backend_value="models/unknown.safetensors",
                display_name="Unknown",
                base_model=None,
            ),
        ),
    )

    model = _prepared_model(source)
    source.save_current_dimensions_for_model(1536, 1024)

    assert model.model_save_label is None
    assert model.sections == ()
    assert repository.presets == ()


def test_source_matches_checkpoint_by_basename_stem() -> None:
    """Comfy checkpoint values may be bare filenames while catalog values are paths."""

    repository = _MemoryRepository()
    source = _source(
        repository,
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        catalog=(
            _model_item(
                backend_value="subdir/illustrious.safetensors",
                display_name="Illustrious XL",
                base_model="Illustrious",
            ),
        ),
    )

    assert _prepared_model(source).model_save_label == "Illustrious"


def test_source_falls_back_to_global_when_checkpoint_catalog_unavailable() -> None:
    """Unavailable checkpoint context should keep global dimension presets usable."""

    repository = _MemoryRepository(
        (
            _preset(
                "dimension:global",
                short_edge=832,
                long_edge=1216,
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
        )
    )
    source = _source(
        repository,
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        fail_catalog=True,
    )

    model = _prepared_model(source)

    assert model.model_save_label is None
    assert [section.title for section in model.sections] == ["Global"]


def test_source_does_not_list_models_during_menu_model_construction() -> None:
    """Preset menu construction should consume prepared checkpoint context only."""

    repository = _MemoryRepository()
    catalog = _Catalog(
        (
            _model_item(
                backend_value="models/illustrious.safetensors",
                display_name="Illustrious XL",
                base_model="Illustrious",
            ),
        )
    )
    source = _source(
        repository,
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        catalog_service=catalog,
    )

    source.prepare_dimension_preset_menu_model(reason="test")

    assert catalog.list_calls == 0


def _source(
    repository: _MemoryRepository,
    *,
    panel: PanelActiveModelContextController,
    catalog: tuple[ModelCatalogItem, ...] = (),
    fail_catalog: bool = False,
    catalog_service: _Catalog | None = None,
) -> EditorDimensionPresetMenuSource:
    """Return one menu source with deterministic service behavior."""

    ids = iter(("dimension:test-1", "dimension:test-2"))
    service = UserPresetService(
        repository,
        id_factory=lambda: next(ids),
        clock=lambda: "2026-04-20T12:00:00Z",
    )
    catalog_lookup = catalog_service or _Catalog(catalog, fail=fail_catalog)
    active_model_snapshots = PanelActiveModelSnapshotController(
        model_context=panel,
        model_catalog_service=catalog_lookup,
    )
    active_model_snapshots.refresh_from_cache()
    return EditorDimensionPresetMenuSource(
        user_preset_service=service,
        active_model_snapshots=active_model_snapshots,
    )


def _prepared_model(
    source: EditorDimensionPresetMenuSource,
) -> DimensionPresetMenuModel:
    """Prepare and return the current dimension menu model."""

    source.prepare_dimension_preset_menu_model(reason="test")
    model = source.current_dimension_preset_menu_model()
    assert model is not None
    return model


def _panel_for_checkpoint(checkpoint_value: str) -> PanelActiveModelContextController:
    """Return a typed checkpoint context with one checkpoint loader."""

    controller = PanelActiveModelContextController()
    controller.begin_projection(("Base",))
    controller.record_node_inputs(
        cube_alias="Base",
        node_name="checkpoint",
        node_type="CheckpointLoaderSimple",
        inputs={"ckpt_name": checkpoint_value},
    )
    return controller


def _model_item(
    *,
    backend_value: str,
    display_name: str,
    base_model: str | None,
) -> ModelCatalogItem:
    """Return one model catalog item for menu source tests."""

    return ModelCatalogItem(
        kind="checkpoints",
        display_name=display_name,
        display_subtitle=None,
        backend_value=backend_value,
        relative_path=backend_value,
        folder="models",
        basename=backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors"),
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=base_model,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=backend_value,
        collision_count=1,
        has_collision=False,
        search_text=display_name,
    )


def _family(key: str, label: str) -> UserPresetAssociation:
    """Return one CivitAI model-family association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.MODEL_FAMILY,
        provider="civitai",
        key=key,
        label=label,
    )


def _preset(
    preset_id: str,
    *,
    short_edge: int,
    long_edge: int,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic dimension preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.DIMENSION,
        label=f"{short_edge} x {long_edge}",
        payload=DimensionPresetPayload(short_edge=short_edge, long_edge=long_edge),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )
