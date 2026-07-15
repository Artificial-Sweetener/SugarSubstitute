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

"""Characterization tests for editor widget factories behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogSnapshot,
    ModelChoiceCatalogIndex,
    ModelThumbnailVariant,
    RichChoiceResolver,
)
from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.domain.prompt import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
)
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory
import substitute.presentation.editor.panel.factories.field_pipeline as factories
import substitute.presentation.editor.panel.factories.image_factory as image_factory
import substitute.presentation.editor.panel.factories.numeric_factory as numeric_factory
import substitute.presentation.editor.panel.factories.prompt_factory as prompt_factory
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshotController,
)


class _FakeNodeDefinitionGateway:
    """Return deterministic node definitions while recording lookup calls."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store per-node-class definition payloads for test lookups."""

        self._definitions = definitions
        self.calls: list[str] = []

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured payload for one node class."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured required payload for one node class."""

        self.calls.append(node_class)
        return self._definitions.get(node_class, {})


class _Signal:
    """Small Qt-like signal helper for factory tests."""

    def __init__(self) -> None:
        self._slots = []

    def connect(self, slot) -> None:
        """Register a callback."""
        self._slots.append(slot)

    def emit(self, *args) -> None:
        """Emit to all callbacks."""
        for slot in list(self._slots):
            slot(*args)


class _FakeLineEdit:
    """LineEdit test double that records assigned text."""

    def __init__(self, _parent=None) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        """Record the assigned text."""
        self.text = text


class _FakeMaskPicker:
    """MaskPicker test double that records metadata and selected path."""

    def __init__(
        self,
        *,
        parent=None,
        cube_alias=None,
        node_name=None,
    ) -> None:
        """Record constructor arguments supplied by the factory."""

        self.parent = parent
        self.cube_alias = cube_alias
        self.node_name = node_name
        self.mask_path = ""
        self._properties: dict[str, object] = {}

    def set_mask_path(self, path: str) -> None:
        """Record the current mask path."""

        self.mask_path = path

    def setProperty(self, name: str, value: object) -> None:
        """Set a Qt-style dynamic property."""

        self._properties[name] = value

    def property(self, name: str) -> object | None:
        """Return a Qt-style dynamic property."""

        return self._properties.get(name)


class _FakeSpinBox:
    """SpinBox test double for integer factory assertions."""

    def __init__(self, _parent=None) -> None:
        self.symbol_visible = None
        self.minimum = None
        self.maximum = None
        self.step = None
        self.value = None

    def setSymbolVisible(self, visible: bool) -> None:
        """Record symbol visibility."""
        self.symbol_visible = visible

    def setMinimum(self, value: int) -> None:
        """Record minimum."""
        self.minimum = value

    def setMaximum(self, value: int) -> None:
        """Record maximum."""
        self.maximum = value

    def setSingleStep(self, step: int) -> None:
        """Record step."""
        self.step = step

    def setValue(self, value: int) -> None:
        """Record assigned value."""
        self.value = value


class _FakeDoubleSpinBox:
    """DoubleSpinBox test double for float factory assertions."""

    def __init__(self, _parent=None) -> None:
        self.symbol_visible = None
        self.minimum = None
        self.maximum = None
        self.step = None
        self.decimals = None
        self.value = None

    def setSymbolVisible(self, visible: bool) -> None:
        """Record symbol visibility."""
        self.symbol_visible = visible

    def setMinimum(self, value: float) -> None:
        """Record minimum."""
        self.minimum = value

    def setMaximum(self, value: float) -> None:
        """Record maximum."""
        self.maximum = value

    def setSingleStep(self, step: float) -> None:
        """Record step."""
        self.step = step

    def setDecimals(self, decimals: int) -> None:
        """Record decimals."""
        self.decimals = decimals

    def setValue(self, value: float) -> None:
        """Record assigned value."""
        self.value = value


class _FakeComboBox:
    """ComboBox test double for list widget factories."""

    def __init__(self, _parent=None) -> None:
        self.items: list[str] = []
        self.current_text = ""
        self.max_hint_width: int | None = None
        self.add_item_calls = 0
        self.add_items_calls = 0
        self.currentTextChanged = _Signal()

    def addItem(self, text: str) -> None:
        """Append a single item."""
        self.add_item_calls += 1
        self.items.append(text)

    def addItems(self, texts: list[str]) -> None:
        """Append multiple items."""
        self.add_items_calls += 1
        self.items.extend(texts)

    def clear(self) -> None:
        """Clear all items."""
        self.items.clear()
        self.current_text = ""

    def setCurrentText(self, text: str) -> None:
        """Assign current text."""
        self.current_text = text

    def setCurrentIndex(self, index: int) -> None:
        """Assign current text from index when valid."""
        if 0 <= index < len(self.items):
            self.current_text = self.items[index]

    def blockSignals(self, _blocked: bool) -> None:
        """No-op in tests."""
        return

    def setMaxHintWidth(self, width: int | None) -> None:
        """Record the preferred width cap."""
        self.max_hint_width = width


class _FakePromptEditor:
    """PromptEditor test double that records assigned text."""

    def __init__(
        self,
        _parent=None,
        *,
        prompt_autocomplete_gateway=None,
        prompt_wildcard_catalog_gateway=None,
        prompt_syntax_profile=None,
        danbooru_url_import_service=None,
        danbooru_wiki_service=None,
        danbooru_image_preview_service=None,
        danbooru_recent_posts_service=None,
        prompt_lora_catalog_service=None,
        prompt_scheduled_lora_service=None,
        scheduled_lora_resolver=None,
        prompt_feature_profile=None,
        prompt_segment_preset_source=None,
        prompt_spellcheck_service=None,
        thumbnail_asset_repository=None,
        model_metadata_action_handler=None,
        prompt_task_executor_factory=None,
        danbooru_lookup_dispatcher_factory=None,
    ) -> None:
        self.text = ""
        self.prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self.prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self.prompt_syntax_profile = prompt_syntax_profile
        self.danbooru_url_import_service = danbooru_url_import_service
        self.danbooru_wiki_service = danbooru_wiki_service
        self.danbooru_image_preview_service = danbooru_image_preview_service
        self.danbooru_recent_posts_service = danbooru_recent_posts_service
        self.prompt_lora_catalog_service = prompt_lora_catalog_service
        self.prompt_scheduled_lora_service = prompt_scheduled_lora_service
        self.scheduled_lora_resolver = scheduled_lora_resolver
        self.prompt_feature_profile = prompt_feature_profile
        self.prompt_segment_preset_source = prompt_segment_preset_source
        self.prompt_spellcheck_service = prompt_spellcheck_service
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.model_metadata_action_handler = model_metadata_action_handler
        self.prompt_task_executor_factory = prompt_task_executor_factory
        self.danbooru_lookup_dispatcher_factory = danbooru_lookup_dispatcher_factory

    def setPlainText(self, text: str) -> None:
        """Record the assigned prompt text."""

        self.text = text


class _FakeModelPickerField:
    """ModelPickerField test double that records constructor inputs."""

    def __init__(
        self,
        parent=None,
        *,
        choice_source,
        thumbnail_asset_repository=None,
        current_value: str = "",
        search_placeholder: str = "Search models",
        metadata_action_handler=None,
        thumbnail_preload_route_factory=None,
    ) -> None:
        self.parent = parent
        self.choice_source = choice_source
        self.resolution = choice_source.current_resolution()
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.current_value = current_value
        self.search_placeholder = search_placeholder
        self.metadata_action_handler = metadata_action_handler
        self.thumbnail_preload_route_factory = thumbnail_preload_route_factory

    def currentText(self) -> str:
        """Return the configured backend value."""

        return self.current_value

    def setCurrentText(self, value: str) -> None:
        """Assign the configured backend value."""

        self.current_value = value


class _FakeModelCatalog:
    """Return deterministic model catalog rows for factory tests."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store fake catalog rows."""

        self._items = items
        self.list_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def replace_items(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Replace fake catalog rows for stale-cache regression tests."""

        self._items = items

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return rows matching the requested model kind."""

        self.list_calls.append(kind)
        return tuple(item for item in self._items if item.kind == kind)

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return rows matching the refreshed model kind."""

        self.refresh_calls.append(kind)
        return self.list_models(kind)

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached rows matching the requested model kind."""

        return tuple(item for item in self._items if item.kind == kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached snapshot for one model kind."""

        return ModelCatalogSnapshot(
            kind=kind,
            items=self.cached_models(kind) or (),
            generation=1,
        )

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a nonblocking cached snapshot for one model kind."""

        return self.cached_snapshot(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation in deterministic tests."""

        _ = kind


class _RefreshOnlyModelCatalog(_FakeModelCatalog):
    """Expose model rows only when the factory forces a refresh."""

    def __init__(self, refresh_items: tuple[ModelCatalogItem, ...]) -> None:
        """Store rows that represent backend-ready refreshed metadata."""

        super().__init__(())
        self._refresh_items = refresh_items
        self.refresh_calls: list[str] = []

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Publish rows for the requested kind during forced refresh."""

        self.refresh_calls.append(kind)
        self.replace_items(self._refresh_items)
        return self.list_models(kind)

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return no cached rows until an explicit refresh publishes them."""

        return tuple(item for item in self._items if item.kind == kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return no canonical cached snapshot until refresh publishes rows."""

        rows = self.cached_models(kind)
        if not rows:
            return None
        return ModelCatalogSnapshot(kind=kind, items=rows, generation=1)

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a nonblocking cached snapshot only after refresh."""

        return self.cached_snapshot(kind)


def _rich_choice_resolver(catalog: _FakeModelCatalog) -> RichChoiceResolver:
    """Return a rich choice resolver backed by the fake model catalog."""

    return RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=catalog)
    )


def _model_choice_controller(
    catalog: _FakeModelCatalog | None,
    resolver: RichChoiceResolver | None = None,
) -> PanelModelChoiceSnapshotController:
    """Return a model-choice snapshot controller for factory tests."""

    return PanelModelChoiceSnapshotController(
        model_catalog_service=catalog,
        model_choice_resolver=resolver
        or (_rich_choice_resolver(catalog) if catalog else None),
    )


def _model_item(
    kind: str,
    value: str,
    title: str,
    *,
    thumbnail_variants: tuple[ModelThumbnailVariant, ...] = (),
) -> ModelCatalogItem:
    """Return one minimal model catalog item for factory tests."""

    basename = value.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".safetensors")
    folder = value.rsplit("\\", 1)[0] if "\\" in value else ""
    return ModelCatalogItem(
        kind=kind,
        display_name=title,
        display_subtitle=None,
        backend_value=value,
        relative_path=value,
        folder=folder,
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=thumbnail_variants,
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{title} {value}".replace("\\", "/").casefold(),
    )


def _thumbnail_variant(storage_key: str) -> ModelThumbnailVariant:
    """Return one prepared thumbnail reference for factory tests."""

    return ModelThumbnailVariant(
        size=768,
        storage_key=storage_key,
        width=768,
        height=160,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=768 * 160 * 4,
    )


def test_widget_factory_int_uses_lineedit_for_overflow(monkeypatch) -> None:
    """INT values outside 32-bit range should use LineEdit fallback."""
    monkeypatch.setattr(numeric_factory, "LineEdit", _FakeLineEdit)
    monkeypatch.setattr(numeric_factory, "SpinBox", _FakeSpinBox)

    widget = factories.widget_factory_int(
        parent=None,
        node_name="node",
        key="seed",
        value=3_000_000_000,
        field_meta={},
        field_type="INT",
        constraints={},
    )

    assert isinstance(widget, _FakeLineEdit)
    assert widget.text == "3000000000"


def test_widget_factory_int_configures_spinbox_when_in_range(monkeypatch) -> None:
    """In-range INT values should produce a configured SpinBox."""
    monkeypatch.setattr(numeric_factory, "LineEdit", _FakeLineEdit)
    monkeypatch.setattr(numeric_factory, "SpinBox", _FakeSpinBox)

    widget = factories.widget_factory_int(
        parent=None,
        node_name="node",
        key="steps",
        value=42,
        field_meta={},
        field_type="INT",
        constraints={"min": 1, "max": 100, "step": 3},
    )

    assert isinstance(widget, _FakeSpinBox)
    assert widget.symbol_visible is False
    assert widget.minimum == 1
    assert widget.maximum == 100
    assert widget.step == 3
    assert widget.value == 42


def test_widget_factory_float_uses_decimal_policy_from_step(monkeypatch) -> None:
    """Float factory should use 0 decimals for integer step and 2 otherwise."""
    monkeypatch.setattr(numeric_factory, "DoubleSpinBox", _FakeDoubleSpinBox)

    integer_step_widget = factories.widget_factory_float(
        parent=None,
        node_name="node",
        key="cfg",
        value=8,
        field_meta={},
        field_type="FLOAT",
        constraints={"step": 1.0},
    )
    fractional_step_widget = factories.widget_factory_float(
        parent=None,
        node_name="node",
        key="cfg",
        value=8.5,
        field_meta={},
        field_type="FLOAT",
        constraints={"step": 0.25},
    )

    assert isinstance(integer_step_widget, _FakeDoubleSpinBox)
    assert isinstance(fractional_step_widget, _FakeDoubleSpinBox)
    assert integer_step_widget.decimals == 0
    assert fractional_step_widget.decimals == 2


def test_widget_factory_spinner_slider_treats_none_constraints_as_missing(
    monkeypatch,
) -> None:
    """Spinner/slider fields should tolerate explicit None constraint values."""

    captured: dict[str, object] = {}

    def _fake_spinner_slider(parent, value, min_val, max_val, step_val):
        """Record spinner/slider numeric arguments."""

        captured["parent"] = parent
        captured["value"] = value
        captured["min"] = min_val
        captured["max"] = max_val
        captured["step"] = step_val
        return object()

    monkeypatch.setattr(
        numeric_factory, "_build_spinner_slider_widget", _fake_spinner_slider
    )

    widget = factories.widget_factory_spinner_slider(
        parent=None,
        node_name="detailer",
        key="denoise",
        value=0.5,
        field_meta={},
        field_type="FLOAT",
        constraints={"min": None, "max": None, "step": None},
    )

    assert widget is not None
    assert captured["min"] == 0.0
    assert captured["max"] == 1.0
    assert captured["step"] == 0.01


def test_widget_factory_spinner_slider_matches_scale_factor_label(monkeypatch) -> None:
    """Spinner/slider selection should use the visible label when keys are generic."""

    captured: dict[str, object] = {}

    def _fake_spinner_slider(parent, value, min_val, max_val, step_val):
        """Record spinner/slider numeric arguments for label-based matching."""

        captured["parent"] = parent
        captured["value"] = value
        captured["min"] = min_val
        captured["max"] = max_val
        captured["step"] = step_val
        return object()

    monkeypatch.setattr(
        numeric_factory, "_build_spinner_slider_widget", _fake_spinner_slider
    )

    widget = factories.widget_factory_spinner_slider(
        parent=None,
        node_name="upscale_by_factor",
        key="value",
        value=1.5,
        field_meta={"label": "Scale Factor"},
        field_type="FLOAT",
        constraints={"min": 0.25, "max": 3.0, "step": 0.05},
    )

    assert widget is not None
    assert captured == {
        "parent": None,
        "value": 1.5,
        "min": 0.25,
        "max": 3.0,
        "step": 0.05,
    }


def test_widget_factory_spinner_slider_declines_qt_unsafe_range(monkeypatch) -> None:
    """Spinner/slider rendering should not build ranges Qt cannot represent."""

    def _fake_spinner_slider(parent, value, min_val, max_val, step_val):
        """Fail if the factory attempts construction with unsafe slider bounds."""

        _ = (parent, value, min_val, max_val, step_val)
        pytest.fail("Unsafe spinner/slider range should be declined before build.")

    monkeypatch.setattr(
        numeric_factory, "_build_spinner_slider_widget", _fake_spinner_slider
    )

    widget = factories.widget_factory_spinner_slider(
        parent=None,
        node_name="upscale_by_factor",
        key="value",
        value=1.5,
        field_meta={"label": "Scale Factor"},
        field_type="FLOAT",
        constraints={
            "min": -9_223_372_036_854_775_807,
            "max": 9_223_372_036_854_775_807,
            "step": 0.1,
        },
    )

    assert widget is None


class _FakePromptAutocompleteGateway:
    """Return empty autocomplete results for focused factory tests."""

    @staticmethod
    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        _ = (prefix, limit)
        return ()


def test_build_prompt_editor_widget_sets_assigned_text_and_gateway(monkeypatch) -> None:
    """Prompt-editor factory should initialize the widget text and inject the gateway."""

    monkeypatch.setattr(prompt_factory, "PromptEditor", _FakePromptEditor)
    gateway = _FakePromptAutocompleteGateway()
    wildcard_gateway = object()
    syntax_profile = object()
    feature_profile = PromptEditorFeatureProfile.enabled_profile(())

    widget = prompt_factory.build_prompt_editor_widget(
        parent=None,
        value="hello world",
        prompt_autocomplete_gateway=gateway,
        prompt_wildcard_catalog_gateway=wildcard_gateway,
        prompt_syntax_profile=syntax_profile,
        prompt_feature_profile=feature_profile,
    )

    assert isinstance(widget, _FakePromptEditor)
    assert widget.text == "hello world"
    assert widget.prompt_autocomplete_gateway is gateway
    assert widget.prompt_wildcard_catalog_gateway is wildcard_gateway
    assert widget.prompt_syntax_profile is syntax_profile
    assert widget.prompt_feature_profile is feature_profile


def test_build_widget_for_field_behavior_resolves_prompt_syntax_profile_from_style(
    monkeypatch,
) -> None:
    """Prompt-box fields should derive the editor syntax profile from field behavior style."""

    monkeypatch.setattr(prompt_factory, "PromptEditor", _FakePromptEditor)
    widget = factories.build_widget_for_field_behavior(
        parent=None,
        field_behavior=FieldBehavior(
            field_key="prompt_template",
            presentation=FieldPresentation.PROMPT_BOX,
            style={"prompt_syntaxes": ["emphasis", "wildcard"]},
        ),
        node_name="positive_prompt",
        key="prompt_template",
        value="hello world",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
    )

    assert isinstance(widget, _FakePromptEditor)
    assert widget.prompt_syntax_profile.enabled_syntaxes == ("emphasis", "wildcard")


def test_build_widget_for_field_behavior_passes_prompt_feature_profile(
    monkeypatch,
) -> None:
    """Prompt-box fields should receive the resolved prompt feature profile."""

    monkeypatch.setattr(prompt_factory, "PromptEditor", _FakePromptEditor)
    feature_profile = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(
                feature=PromptEditorFeature.EMPHASIS,
                enabled=True,
            ),
        )
    )

    widget = factories.build_widget_for_field_behavior(
        parent=None,
        field_behavior=FieldBehavior(
            field_key="prompt_template",
            presentation=FieldPresentation.PROMPT_BOX,
            style={"prompt_syntaxes": ["emphasis"]},
        ),
        node_name="positive_prompt",
        key="prompt_template",
        value="hello world",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        prompt_feature_profile=feature_profile,
    )

    assert isinstance(widget, _FakePromptEditor)
    assert widget.prompt_feature_profile is feature_profile


def test_build_widget_for_field_behavior_builds_model_picker_from_presentation(
    monkeypatch,
) -> None:
    """MODEL_PICKER presentation should build the explicit model picker field."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    model_catalog = _FakeModelCatalog(
        (_model_item("checkpoints", "models/base.safetensors", "Civit Base"),)
    )
    thumbnail_repository = object()
    thumbnail_route_factory = object()

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(
            field_key="ckpt_name",
            presentation=FieldPresentation.MODEL_PICKER,
            style={"model_kind": "checkpoints"},
        ),
        node_name="checkpoint",
        key="ckpt_name",
        value="models/base.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(model_catalog),
        thumbnail_asset_repository=thumbnail_repository,
        model_picker_thumbnail_preload_route_factory=thumbnail_route_factory,
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.parent == "parent"
    assert widget.resolution.matched_kinds == ("checkpoints",)
    assert widget.thumbnail_asset_repository is thumbnail_repository
    assert widget.thumbnail_preload_route_factory is thumbnail_route_factory
    assert widget.currentText() == "models/base.safetensors"
    assert model_catalog.list_calls == []


def test_explicit_model_picker_reuses_shared_rich_choice_resolution(
    monkeypatch,
) -> None:
    """MODEL_PICKER fields should consume prepared snapshots without catalog loading."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    model_catalog = _FakeModelCatalog(
        (
            _model_item("checkpoints", "models/base.safetensors", "Civit Base"),
            _model_item("checkpoints", "models/refiner.safetensors", "Refiner"),
        )
    )
    resolver = _rich_choice_resolver(model_catalog)
    controller = _model_choice_controller(model_catalog, resolver)
    behavior = FieldBehavior(
        field_key="ckpt_name",
        presentation=FieldPresentation.MODEL_PICKER,
        style={"model_kind": "checkpoints"},
    )

    first_widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=behavior,
        node_name="checkpoint",
        key="ckpt_name",
        value="models/base.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=controller,
    )
    second_widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=behavior,
        node_name="checkpoint",
        key="ckpt_name",
        value="models/refiner.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=controller,
    )

    assert isinstance(first_widget, _FakeModelPickerField)
    assert isinstance(second_widget, _FakeModelPickerField)
    assert [item.value for item in first_widget.resolution.items] == [
        "models/base.safetensors",
        "models/refiner.safetensors",
    ]
    assert [item.value for item in second_widget.resolution.items] == [
        "models/base.safetensors",
        "models/refiner.safetensors",
    ]
    assert model_catalog.list_calls == []


def test_build_widget_for_field_behavior_builds_rich_picker_for_lora_list(
    monkeypatch,
) -> None:
    """Model-backed LIST values should build the rich picker without node patches."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item("loras", "animeLineart.safetensors", "Anime Lineart"),
            _model_item("loras", "stylePack.safetensors", "Style Pack"),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="lora_name"),
        node_name="lora_loader",
        key="lora_name",
        value="animeLineart.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="SomeLoraLoader",
        field_info=[
            ["animeLineart.safetensors", "stylePack.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("loras",)
    assert [item.value for item in widget.resolution.items] == [
        "animeLineart.safetensors",
        "stylePack.safetensors",
    ]


def test_build_widget_for_field_behavior_keeps_cold_model_list_as_model_picker(
    monkeypatch,
) -> None:
    """Model-backed LIST fields should not become plain combos while metadata is cold."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    monkeypatch.setattr(
        choice_factory,
        "ComboBox",
        lambda *_args, **_kwargs: pytest.fail("model field fell back to ComboBox"),
    )
    catalog = _FakeModelCatalog(())
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("checkpoints",)
    assert widget.resolution.enriched_count == 0
    assert [item.value for item in widget.resolution.items] == [
        "base-a.safetensors",
        "base-b.safetensors",
    ]


def test_model_list_picker_loads_refreshed_thumbnails_before_first_render(
    monkeypatch,
) -> None:
    """Known model LIST fields should defer thumbnail enrichment to source refresh."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    monkeypatch.setattr(
        choice_factory,
        "ComboBox",
        lambda *_args, **_kwargs: pytest.fail("model field fell back to ComboBox"),
    )
    thumbnail = _thumbnail_variant("checkpoints/base-a/banner")
    catalog = _RefreshOnlyModelCatalog(
        (
            _model_item(
                "checkpoints",
                "base-a.safetensors",
                "Base A",
                thumbnail_variants=(thumbnail,),
            ),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert catalog.refresh_calls == []
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.enriched_count == 0
    assert widget.resolution.items[0].thumbnail_variants == ()

    refreshed = widget.choice_source.refresh()

    assert catalog.refresh_calls == ["checkpoints"]
    assert refreshed.enriched_count == 1
    assert refreshed.items[0].thumbnail_variants == (thumbnail,)


def test_cold_model_list_picker_source_upgrades_on_refresh(monkeypatch) -> None:
    """Cold first-render model pickers should enrich through normal refresh."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(())
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )
    catalog.replace_items(
        (
            _model_item("checkpoints", "base-a.safetensors", "Base A"),
            _model_item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )

    refreshed = widget.choice_source.refresh()

    assert isinstance(widget, _FakeModelPickerField)
    assert refreshed.should_use_rich_picker is True
    assert refreshed.matched_kinds == ("checkpoints",)
    assert refreshed.enriched_count == 2


def test_build_widget_for_field_behavior_recovers_from_stale_empty_rich_cache(
    monkeypatch,
) -> None:
    """Model LIST rendering should recover when the resolver was loaded empty early."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(())
    resolver = _rich_choice_resolver(catalog)
    resolver.resolve(("base-a.safetensors", "base-b.safetensors"))
    catalog.replace_items(
        (
            _model_item("checkpoints", "base-a.safetensors", "Base A"),
            _model_item("checkpoints", "base-b.safetensors", "Base B"),
        )
    )

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        node_name="checkpoint",
        key="ckpt_name",
        value="base-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        field_info=[
            ["base-a.safetensors", "base-b.safetensors"],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("checkpoints",)


def test_build_widget_for_field_behavior_builds_rich_picker_for_anima_diffusion_model_list(
    monkeypatch,
) -> None:
    """Anima diffusion model LIST values should build the shared rich picker."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item(
                "diffusion_models",
                "Anima\\anima_base_V10.safetensors",
                "Anima Base",
            ),
            _model_item(
                "diffusion_models",
                "Anima\\animaOfficial_preview3Base.safetensors",
                "Anima Preview",
            ),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="diffusion_model"),
        node_name="load_anima",
        key="diffusion_model",
        value="Anima\\anima_base_V10.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="SimpleSyrup.SimpleLoadAnima",
        field_info=[
            [
                "Anima\\anima_base_V10.safetensors",
                "Anima\\animaOfficial_preview3Base.safetensors",
            ],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("diffusion_models",)
    assert widget.currentText() == "Anima\\anima_base_V10.safetensors"
    assert [item.value for item in widget.resolution.items] == [
        "Anima\\anima_base_V10.safetensors",
        "Anima\\animaOfficial_preview3Base.safetensors",
    ]


def test_build_widget_for_field_behavior_attempts_rich_picker_for_generic_diffusion_model_key(
    monkeypatch,
) -> None:
    """Generic diffusion model key fragments should attempt rich picker enrichment."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item(
                "diffusion_models",
                "models\\diffusion-a.safetensors",
                "Diffusion A",
            ),
            _model_item(
                "diffusion_models",
                "models\\diffusion-b.safetensors",
                "Diffusion B",
            ),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="diffusion_model"),
        node_name="load_diffusion",
        key="diffusion_model",
        value="models\\diffusion-a.safetensors",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="SomeDiffusionLoader",
        field_info=[
            [
                "models\\diffusion-a.safetensors",
                "models\\diffusion-b.safetensors",
            ],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("diffusion_models",)
    assert widget.currentText() == "models\\diffusion-a.safetensors"


def test_build_widget_for_field_behavior_keeps_vae_literals_in_rich_picker(
    monkeypatch,
) -> None:
    """VAE LIST values should qualify while special literals remain choices."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    catalog = _FakeModelCatalog(
        (
            _model_item("vae", "ClearVAE.safetensors", "ClearVAE"),
            _model_item("vae", "Illustrious\\neptunia.safetensors", "Neptunia"),
        )
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent="parent",
        field_behavior=FieldBehavior(field_key="vae_name"),
        node_name="vae",
        key="vae_name",
        value="pixel_space",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="VAELoader",
        field_info=[
            [
                "ClearVAE.safetensors",
                "Illustrious\\neptunia.safetensors",
                "pixel_space",
            ],
            {},
        ],
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.items[2].value == "pixel_space"
    assert widget.resolution.items[2].is_enriched is False


def test_build_widget_for_field_behavior_keeps_non_model_lists_as_combo(
    monkeypatch,
) -> None:
    """Non-model LIST values should still fall back to the plain combo factory."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    catalog = _FakeModelCatalog(
        (_model_item("checkpoints", "model-a.safetensors", "Model A"),)
    )
    resolver = _rich_choice_resolver(catalog)

    widget = factories.build_widget_for_field_behavior(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        field_behavior=FieldBehavior(field_key="method"),
        node_name="vectorscopecc",
        key="method",
        value="Straight",
        field_meta={},
        prompt_autocomplete_gateway=_FakePromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=object(),
        model_choice_snapshot_controller=_model_choice_controller(catalog, resolver),
        field_type="LIST",
        node_type="VectorscopeCC",
        field_info=[["Straight", "Cross", "Ones"], {}],
    )

    assert isinstance(widget, _FakeComboBox)
    assert widget.current_text == "Straight"
    assert widget.max_hint_width == choice_factory._EDITOR_COMBO_MAX_HINT_WIDTH


def test_widget_factory_list_str_caps_generic_editor_combo_width(monkeypatch) -> None:
    """Generic editor combo boxes should receive the standard max hint width."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)

    combo = factories.widget_factory_list_str(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        node_name="node",
        key="mode",
        value="Short",
        field_meta={},
        field_type="LIST",
        node_type="CustomNode",
        node_definition_gateway=_FakeNodeDefinitionGateway({}),
        field_info=[
            [
                "Short",
                "An exceptionally long option label that should not widen rows",
            ],
            {},
        ],
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.max_hint_width == choice_factory._EDITOR_COMBO_MAX_HINT_WIDTH


def test_widget_factory_list_str_sampler_switches_between_link_and_literal(
    monkeypatch,
) -> None:
    """Sampler list combobox should prepare link data without mutating node data."""
    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {"required": {"sampler_name": [["euler", "heun"]]}}
                }
            }
        },
    )

    parent = SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={})
    node_data = {
        "inputs": {},
        "sampler_links": [
            {"from_cube": "A", "from_node": "ksampler", "label": "link:A"}
        ],
        "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
        "cube_alias": "B",
    }
    field_meta = {"cube_alias": "B", "node_data": node_data}

    combo = factories.widget_factory_list_str(
        parent=parent,
        node_name="ksampler",
        key="sampler_name",
        value="euler",
        field_meta=field_meta,
        field_type="LIST",
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.current_text == "link:A"
    assert parent.sampler_link_widgets[("B", "ksampler")] is combo
    assert getattr(combo, "_editor_choice_values_by_label")["heun"] == "heun"
    assert getattr(combo, "_editor_choice_values_by_label")["link:A"] == {
        "from_cube": "A",
        "from_node": "ksampler",
    }

    combo.currentTextChanged.emit("heun")
    assert node_data["inputs"] == {}
    assert node_data["sampler_link"] == {"from_cube": "A", "from_node": "ksampler"}

    combo.currentTextChanged.emit("link:A")
    assert node_data["sampler_link"] == {"from_cube": "A", "from_node": "ksampler"}
    assert node_data["inputs"] == {}


def test_widget_factory_list_str_falls_back_to_cube_field_info(monkeypatch) -> None:
    """LIST factories should use cube field info when live options are unavailable."""
    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway({})

    combo = factories.widget_factory_list_str(
        parent=SimpleNamespace(
            sampler_link_widgets={},
            scheduler_link_widgets={},
        ),
        node_name="ksampler",
        key="sampler_name",
        value="heun",
        field_meta={},
        field_type="LIST",
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
        field_info=[["euler", "heun"], {"default": "euler"}],
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == ["euler", "heun"]
    assert combo.current_text == "heun"
    assert combo.add_item_calls == 0
    assert combo.add_items_calls == 1


def test_widget_factory_list_str_renders_combo_field_info(monkeypatch) -> None:
    """COMBO fields should render as the same generic dropdown control as LIST fields."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway({})

    combo = factories.widget_factory_list_str(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        node_name="load_upscale_model",
        key="model_name",
        value="R-ESRGAN 4x+ Anime6B.pth",
        field_meta={},
        field_type="COMBO",
        field_info=[
            "COMBO",
            {
                "options": [
                    "ESRGAN_4x.pth",
                    "R-ESRGAN 4x+ Anime6B.pth",
                ]
            },
        ],
        node_type="UpscaleModelLoader",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == ["ESRGAN_4x.pth", "R-ESRGAN 4x+ Anime6B.pth"]
    assert combo.current_text == "R-ESRGAN 4x+ Anime6B.pth"


def test_widget_factory_list_str_rejects_current_value_when_no_option_source_exists(
    monkeypatch,
) -> None:
    """LIST factories should not turn the current value into a choice option."""
    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway({})

    with pytest.raises(RuntimeError, match="Failed to resolve live Comfy options"):
        factories.widget_factory_list_str(
            parent=SimpleNamespace(),
            node_name="ksampler",
            key="sampler_name",
            value="euler",
            field_meta={},
            field_type="LIST",
            node_type="KSampler",
            node_definition_gateway=node_definition_gateway,
            field_info=None,
        )


def test_widget_factory_list_str_raises_for_empty_value_without_options(
    monkeypatch,
) -> None:
    """LIST factories should still fail when no choices or current value exist."""
    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)

    with pytest.raises(RuntimeError):
        factories.widget_factory_list_str(
            parent=SimpleNamespace(),
            node_name="ksampler",
            key="sampler_name",
            value="",
            field_meta={},
            field_type="LIST",
            node_type="KSampler",
            node_definition_gateway=_FakeNodeDefinitionGateway({}),
            field_info=None,
        )


def test_widget_factory_list_str_non_link_fields_use_application_resolved_value(
    monkeypatch,
) -> None:
    """Non-link list widgets should render the effective value chosen upstream."""
    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "CheckpointLoaderSimple": {
                "CheckpointLoaderSimple": {
                    "input": {
                        "required": {
                            "ckpt_name": [
                                [
                                    "Illustrious\\tNoobnai3_v9.safetensors",
                                    "OtherModel.safetensors",
                                ]
                            ]
                        }
                    }
                }
            }
        }
    )

    combo = factories.widget_factory_list_str(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        node_name="checkpoint",
        key="ckpt_name",
        value="OtherModel.safetensors",
        field_meta={},
        field_type="LIST",
        node_type="CheckpointLoaderSimple",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.current_text == "OtherModel.safetensors"


def test_widget_factory_list_str_ultralytics_like_fields_remain_plain_combo(
    monkeypatch,
) -> None:
    """Model-like LIST fields must not receive the picker upgrade by type alone."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "UltralyticsDetectorProvider": {
                "UltralyticsDetectorProvider": {
                    "input": {
                        "required": {
                            "model_name": [
                                ["bbox/yolo.pt", "segm/yolo-seg.pt"],
                            ]
                        }
                    }
                }
            }
        }
    )

    combo = factories.widget_factory_list_str(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        node_name="ultralytics",
        key="model_name",
        value="bbox/yolo.pt",
        field_meta={},
        field_type="LIST",
        node_type="UltralyticsDetectorProvider",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.current_text == "bbox/yolo.pt"


def test_widget_factory_list_str_uses_live_options_for_compact_dynamic_marker(
    monkeypatch,
) -> None:
    """Compact dynamic LIST fields should get their choices from live definitions."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {
                        "required": {
                            "sampler_name": [
                                ["euler", "heun"],
                                {"default": "euler"},
                            ]
                        }
                    }
                }
            }
        }
    )

    combo = factories.widget_factory_list_str(
        parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
        node_name="ksampler",
        key="sampler_name",
        value="heun",
        field_meta={"node_data": {"inputs": {"sampler_name": "heun"}}},
        field_type="LIST",
        field_info=["LIST", {"dynamic": True}],
        node_type="KSampler",
        node_definition_gateway=node_definition_gateway,
    )

    assert isinstance(combo, _FakeComboBox)
    assert combo.items == ["euler", "heun"]
    assert combo.current_text == "heun"


def test_widget_factory_list_str_rejects_dynamic_marker_without_live_options(
    monkeypatch,
) -> None:
    """Compact dynamic LIST fields must not render current values as options."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)

    with pytest.raises(RuntimeError, match="Failed to resolve live Comfy options"):
        factories.widget_factory_list_str(
            parent=SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={}),
            node_name="ksampler",
            key="sampler_name",
            value="heun",
            field_meta={
                "options_resolved": False,
                "options_unavailable_reason": "missing_list_options",
            },
            field_type="LIST",
            field_info=["LIST", {"dynamic": True}],
            node_type="KSampler",
            node_definition_gateway=_FakeNodeDefinitionGateway({}),
        )


def test_build_mask_picker_widget_sets_refresh_matching_metadata(monkeypatch) -> None:
    """Factory-created mask pickers should expose cube/node metadata for refresh."""

    monkeypatch.setattr(image_factory, "MaskPicker", _FakeMaskPicker)

    picker = image_factory.build_mask_picker_widget(
        parent="parent",
        node_name="load_image_as_mask",
        key="image",
        value="E:/masks/current.png",
        field_meta={"cube_alias": "Inpaint"},
    )

    assert picker.cube_alias == "Inpaint"
    assert picker.node_name == "load_image_as_mask"
    assert picker.mask_path == "E:/masks/current.png"
    assert picker.property("input_metadata") == {
        "cube_alias": "Inpaint",
        "node_name": "load_image_as_mask",
        "key": "image",
    }
