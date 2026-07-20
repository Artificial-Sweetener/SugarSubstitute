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

"""Contract tests for editor saved prompt segment menu source composition."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
)
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_source import (
    EditorPromptSegmentPresetMenuSource,
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

        return self.items

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return cached checkpoint rows without loading the catalog."""

        return self.cached_snapshot(kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return cached checkpoint rows or fail like the catalog cache."""

        if self.fail:
            raise RuntimeError("checkpoint catalog unavailable")
        return ModelCatalogSnapshot(kind=kind, items=self.items, generation=3)

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached checkpoint rows for legacy cache readers."""

        if self.fail:
            raise RuntimeError("checkpoint catalog unavailable")
        return self.items

    def invalidate(self, kind: str | None = None) -> None:
        """Record no state for invalidation in tests."""

        _ = kind


def test_source_lists_prompt_segments_by_specificity() -> None:
    """The source should expose exact, family, then global prompt segment sections."""

    exact = _checkpoint("200", "Wrong Long Name")
    family = _family("illustrious", "Illustrious")
    repository = _MemoryRepository(
        (
            _preset(
                "prompt:global",
                label="Global",
                text="global words",
                associations=(GLOBAL_PRESET_ASSOCIATION,),
            ),
            _preset(
                "prompt:family",
                label="Family",
                text="family words",
                associations=(family,),
            ),
            _preset(
                "prompt:exact",
                label="Exact",
                text="exact words",
                associations=(exact,),
            ),
        )
    )
    source = _source(
        repository,
        panel=_panel_for_checkpoint("models/illustrious.safetensors"),
        catalog=(
            _model_item(
                backend_value="models/illustrious.safetensors",
                display_name="Wrong Long Name",
                base_model="Illustrious",
                provider_model_version_id="200",
            ),
        ),
    )

    snapshot = source.list_prompt_segment_presets()
    model = snapshot.menu_model

    assert [section.title for section in model.sections] == [
        "Checkpoint",
        "Illustrious",
        "Global",
    ]
    assert [section.presets[0].text for section in model.sections] == [
        "exact words",
        "family words",
        "global words",
    ]


def test_source_save_scopes_include_global_family_and_exact_checkpoint() -> None:
    """Save scopes should include compact choices for the active checkpoint."""

    source = _source(
        _MemoryRepository(),
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        catalog=(
            _model_item(
                backend_value="models/illustrious.safetensors",
                display_name="Wrong Long Name",
                display_subtitle="Version Alpha",
                base_model="Illustrious",
                provider_model_version_id="200",
            ),
        ),
    )

    snapshot = source.list_prompt_segment_presets()
    scopes = snapshot.menu_model.save_scopes

    assert [scope.title for scope in scopes] == [
        "Global",
        "Illustrious",
        "Checkpoint",
    ]
    assert render_source_application_text(scopes[1].full_label) == (
        "Base model: Illustrious"
    )
    assert render_source_application_text(scopes[2].full_label) == (
        "Checkpoint: Wrong Long Name - Version Alpha"
    )


def test_source_save_scopes_include_exact_diffusion_model() -> None:
    """Standalone diffusion-model context should receive accurate save scopes."""

    source = _source(
        _MemoryRepository(),
        panel=_panel_for_diffusion_model("Anima/hassakuAnima_v11.safetensors"),
        catalog=(
            _model_item(
                kind="diffusion_models",
                backend_value="Anima/hassakuAnima_v11.safetensors",
                display_name="Hassaku Anima V11",
                base_model="Illustrious",
            ),
        ),
    )

    scopes = source.list_prompt_segment_presets().menu_model.save_scopes

    assert [scope.title for scope in scopes] == [
        "Global",
        "Illustrious",
        "Diffusion model",
    ]
    assert render_source_application_text(scopes[-1].full_label) == (
        "Diffusion model: Hassaku Anima V11"
    )


def test_source_saves_prompt_segment_for_selected_scope() -> None:
    """Saving should delegate exact selected text and selected association to the service."""

    repository = _MemoryRepository()
    source = _source(repository, panel=_panel_for_checkpoint("missing.safetensors"))
    scope = source.list_prompt_segment_presets().menu_model.save_scopes[0]

    source.save_prompt_segment(label="Blue eyes", text="blue eyes", scope=scope)

    assert len(repository.presets) == 1
    assert repository.presets[0].payload == PromptStringPresetPayload(text="blue eyes")
    assert repository.presets[0].associations == (GLOBAL_PRESET_ASSOCIATION,)


def test_source_uses_global_only_scopes_when_checkpoint_catalog_unavailable() -> None:
    """Unavailable checkpoint context should preserve global prompt preset support."""

    source = _source(
        _MemoryRepository(
            (
                _preset(
                    "prompt:global",
                    label="Global",
                    text="global words",
                    associations=(GLOBAL_PRESET_ASSOCIATION,),
                ),
            )
        ),
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        catalog=(),
        fail_catalog=True,
    )

    snapshot = source.list_prompt_segment_presets()
    model = snapshot.menu_model

    assert [scope.title for scope in model.save_scopes] == ["Global"]
    assert [section.title for section in model.sections] == ["Global"]
    assert snapshot.catalog_identity.unavailable_reason == "model_catalog_unavailable"


def test_source_does_not_list_models_during_menu_model_construction() -> None:
    """Preset menu construction should consume prepared checkpoint context only."""

    repository = _MemoryRepository()
    catalog = _Catalog(
        (
            _model_item(
                backend_value="models/illustrious.safetensors",
                display_name="Illustrious XL",
                base_model="Illustrious",
                provider_model_version_id="200",
            ),
        )
    )
    source = _source(
        repository,
        panel=_panel_for_checkpoint("illustrious.safetensors"),
        catalog_service=catalog,
    )

    source.list_prompt_segment_presets()

    assert catalog.list_calls == 0


def _source(
    repository: _MemoryRepository,
    *,
    panel: PanelActiveModelContextController,
    catalog: tuple[ModelCatalogItem, ...] = (),
    fail_catalog: bool = False,
    catalog_service: _Catalog | None = None,
) -> EditorPromptSegmentPresetMenuSource:
    """Return one menu source with deterministic service behavior."""

    ids = iter(("prompt:test-1", "prompt:test-2"))
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
    return EditorPromptSegmentPresetMenuSource(
        user_preset_service=service,
        active_model_snapshots=active_model_snapshots,
    )


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


def _panel_for_diffusion_model(model_value: str) -> PanelActiveModelContextController:
    """Return active context with one standalone diffusion model."""

    controller = PanelActiveModelContextController()
    controller.begin_projection(("Base",))
    controller.record_node_inputs(
        cube_alias="Base",
        node_name="models",
        node_type="SimpleSyrup.SimpleLoadAnima",
        inputs={"diffusion_model": model_value},
    )
    return controller


def _model_item(
    *,
    kind: str = "checkpoints",
    backend_value: str,
    display_name: str,
    base_model: str | None,
    display_subtitle: str | None = None,
    provider_model_version_id: str | None = None,
) -> ModelCatalogItem:
    """Return one model catalog item for menu source tests."""

    return ModelCatalogItem(
        kind=kind,
        display_name=display_name,
        display_subtitle=display_subtitle,
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
        provider_name="civitai" if provider_model_version_id is not None else None,
        provider_model_id="100" if provider_model_version_id is not None else None,
        provider_model_version_id=provider_model_version_id,
        provider_model_name=display_name
        if provider_model_version_id is not None
        else None,
        provider_model_version_name=display_subtitle,
    )


def _checkpoint(key: str, label: str) -> UserPresetAssociation:
    """Return one CivitAI model-version association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.PROVIDER_MODEL_VERSION,
        provider="civitai",
        key=key,
        label=label,
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
    text: str,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic prompt string preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.PROMPT_STRING,
        label=label,
        payload=PromptStringPresetPayload(text=text),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )
