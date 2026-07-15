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

"""Contract tests for editor node input preset menu source composition."""

from __future__ import annotations

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    NodeInputPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
)
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
)
from substitute.presentation.editor.panel.menus.node_input_preset_menu_source import (
    EditorNodeInputPresetMenuSource,
    NodeInputPresetMenuModel,
)
from substitute.presentation.editor.panel.context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope


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


def test_source_lists_family_and_global_node_input_sections() -> None:
    """The source should expose active-family presets before global presets."""

    illustrious = _family("illustrious", "Illustrious")
    repository = _MemoryRepository(
        (
            _preset(
                "node_inputs:global",
                label="Balanced",
                node_type="KSampler",
                inputs={"steps": 20},
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
            _preset(
                "node_inputs:family",
                label="Fast Draft",
                node_type="KSampler",
                inputs={"steps": 12},
                associations=(illustrious,),
            ),
            _preset(
                "node_inputs:checkpoint",
                label="Wrong Type",
                node_type="CheckpointLoaderSimple",
                inputs={"ckpt_name": "model.safetensors"},
                associations=(GLOBAL_PRESET_ASSOCIATION,),
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

    model = _prepared_model(source, "KSampler")

    assert [section.title for section in model.sections] == [
        "Illustrious",
        "Global",
    ]
    assert [item.label for item in model.sections[0].presets] == ["Fast Draft"]
    assert [item.label for item in model.sections[1].presets] == ["Balanced"]
    assert model.save_scopes == (
        PresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        ),
        PresetSaveScope(
            title="Illustrious",
            full_label="Base model: Illustrious",
            association=illustrious,
        ),
    )


def test_source_saves_node_inputs_globally() -> None:
    """Global saves should write a named node input preset."""

    repository = _MemoryRepository()
    source = _source(repository, panel=_panel_for_checkpoint("missing.safetensors"))

    source.save_node_input_preset(
        label="Fast Draft",
        node_type="KSampler",
        inputs={"steps": 12},
        scope=PresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        ),
    )

    assert len(repository.presets) == 1
    assert repository.presets[0].payload == NodeInputPresetPayload(
        node_type="KSampler",
        inputs={"steps": 12},
    )
    assert repository.presets[0].associations == (GLOBAL_PRESET_ASSOCIATION,)


def test_source_saves_node_inputs_for_active_model_family() -> None:
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
    scope = _prepared_model(source, "KSampler").save_scopes[1]

    source.save_node_input_preset(
        label="Fast Draft",
        node_type="KSampler",
        inputs={"steps": 12},
        scope=scope,
    )

    assert repository.presets[0].associations == (
        _family("illustrious", "Illustrious"),
    )


def test_source_omits_model_save_scope_when_checkpoint_has_no_family() -> None:
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

    assert _prepared_model(source, "KSampler").save_scopes == (
        PresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        ),
    )


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

    assert _prepared_model(source, "KSampler").save_scopes[1].title == "Illustrious"


def test_source_falls_back_to_global_when_checkpoint_catalog_unavailable() -> None:
    """Unavailable checkpoint context should keep global node presets usable."""

    repository = _MemoryRepository(
        (
            _preset(
                "node_inputs:global",
                label="Balanced",
                node_type="KSampler",
                inputs={"steps": 20},
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
        )
    )
    source = _source(
        repository,
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        fail_catalog=True,
    )

    model = _prepared_model(source, "KSampler")

    assert [scope.title for scope in model.save_scopes] == ["Global"]
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

    _prepared_model(source, "KSampler")

    assert catalog.list_calls == 0


def _source(
    repository: _MemoryRepository,
    *,
    panel: PanelActiveModelContextController,
    catalog: tuple[ModelCatalogItem, ...] = (),
    fail_catalog: bool = False,
    catalog_service: _Catalog | None = None,
) -> EditorNodeInputPresetMenuSource:
    """Return one menu source with deterministic service behavior."""

    ids = iter(("node_inputs:test-1", "node_inputs:test-2"))
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
    return EditorNodeInputPresetMenuSource(
        user_preset_service=service,
        active_model_snapshots=active_model_snapshots,
    )


def _prepared_model(
    source: EditorNodeInputPresetMenuSource,
    node_type: str,
) -> NodeInputPresetMenuModel:
    """Prepare and return one node input preset menu model."""

    source.prepare_node_input_preset_menu_model(
        node_type=node_type,
        reason="test",
    )
    model = source.current_node_input_preset_menu_model(node_type=node_type)
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
    label: str,
    node_type: str,
    inputs: dict[str, object],
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic node input preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.NODE_INPUTS,
        label=label,
        payload=NodeInputPresetPayload(node_type=node_type, inputs=inputs),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )
