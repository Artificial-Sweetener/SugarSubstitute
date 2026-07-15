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

"""Tests for panel choice and model-picker field factory ownership."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogSnapshot,
    ModelChoiceCatalogIndex,
    ModelThumbnailVariant,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.application.node_behavior import FieldBehavior, FieldPresentation
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE
from substitute.presentation.editor.panel.model_choice_snapshot_controller import (
    PanelModelChoiceSnapshot,
    PanelModelChoiceSnapshotController,
    PanelModelChoiceSnapshotRequest,
)
import substitute.presentation.editor.panel.factories.choice_factory as choice_factory
from substitute.presentation.editor.panel.factories.choice_factory import (
    ChoiceFieldBuildRequest,
    ChoiceFieldFactory,
)


class _Signal:
    """Provide the small signal surface needed by combo field tests."""

    def __init__(self) -> None:
        """Create an empty callback list."""

        self._slots: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected callback."""

        self._slots.append(slot)

    def emit(self, *args: object) -> None:
        """Invoke every connected callback with the supplied arguments."""

        for slot in self._slots:
            if callable(slot):
                slot(*args)


class _FakeComboBox:
    """Record combo construction and current-text changes."""

    def __init__(self, parent: object = None) -> None:
        """Store constructor state for assertions."""

        self.parent = parent
        self.items: list[str] = []
        self.current_text = ""
        self.max_hint_width: int | None = None
        self.currentTextChanged = _Signal()

    def setMaxHintWidth(self, width: int | None) -> None:
        """Record the configured dropdown width cap."""

        self.max_hint_width = width

    def addItems(self, items: list[str]) -> None:
        """Append all combo display items."""

        self.items.extend(items)

    def setCurrentText(self, text: str) -> None:
        """Record the selected display text."""

        self.current_text = text


class _FakeModelPickerField:
    """Record model-picker construction inputs."""

    def __init__(
        self,
        parent: object = None,
        *,
        choice_source: Any,
        thumbnail_asset_repository: object | None = None,
        current_value: str = "",
        search_placeholder: str = "Search models",
        metadata_action_handler: object | None = None,
        thumbnail_preload_route_factory: object | None = None,
    ) -> None:
        """Store picker inputs for assertions."""

        self.parent = parent
        self.choice_source = choice_source
        self.resolution = choice_source.current_resolution()
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.current_value = current_value
        self.search_placeholder = search_placeholder
        self.metadata_action_handler = metadata_action_handler
        self.thumbnail_preload_route_factory = thumbnail_preload_route_factory

    def currentText(self) -> str:
        """Return the current backend value."""

        return self.current_value


class _FakeNodeDefinitionGateway:
    """Return deterministic node definitions for choice-option resolution."""

    def __init__(self, definitions: dict[str, dict[str, object]]) -> None:
        """Store definitions by node class."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured node definition payload."""

        return self.get_required_node_definition(node_class)

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return the configured node definition payload."""

        return self._definitions.get(node_class, {})


class _FakeModelCatalog:
    """Return deterministic model catalog rows for model-picker tests."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store model catalog rows."""

        self._items = items
        self.list_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return rows matching the requested model kind."""

        self.list_calls.append(kind)
        return tuple(item for item in self._items if item.kind == kind)

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return rows matching the requested model kind."""

        self.refresh_calls.append(kind)
        return self.list_models(kind)

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return cached rows matching the requested model kind."""

        return tuple(item for item in self._items if item.kind == kind)

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached snapshot for the requested model kind."""

        return ModelCatalogSnapshot(
            kind=kind, items=self.cached_models(kind) or (), generation=1
        )

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a nonblocking cached snapshot for the requested model kind."""

        return self.cached_snapshot(kind)

    def invalidate(self, kind: str | None = None) -> None:
        """Accept invalidation requests from the resolver."""

        _ = kind


def _model_item(kind: str, value: str, title: str) -> ModelCatalogItem:
    """Return one minimal model catalog item."""

    basename = value.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".safetensors")
    return ModelCatalogItem(
        kind=kind,
        display_name=title,
        display_subtitle=None,
        backend_value=value,
        relative_path=value,
        folder="",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{title} {value}".replace("\\", "/").casefold(),
    )


def _thumbnail_model_item(kind: str, value: str, title: str) -> ModelCatalogItem:
    """Return one minimal model catalog item with a banner thumbnail."""

    item = _model_item(kind, value, title)
    return ModelCatalogItem(
        kind=item.kind,
        display_name=item.display_name,
        display_subtitle=item.display_subtitle,
        backend_value=item.backend_value,
        relative_path=item.relative_path,
        folder=item.folder,
        basename=item.basename,
        extension=item.extension,
        thumbnail_variants=(
            ModelThumbnailVariant(
                size=768,
                storage_key=f"{value}:banner",
                width=768,
                height=160,
                content_format="png",
                byte_size=1024,
                role=BANNER_THUMBNAIL_ROLE,
            ),
        ),
        base_model=item.base_model,
        trained_words=item.trained_words,
        tags=item.tags,
        model_page_url=item.model_page_url,
        collision_key=item.collision_key,
        collision_count=item.collision_count,
        has_collision=item.has_collision,
        search_text=item.search_text,
    )


class _MetadataBootstrapCatalog(_FakeModelCatalog):
    """Expose local metadata rows when the canonical catalog is cold."""

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Simulate a cold canonical catalog."""

        _ = kind
        return None

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Simulate a cold nonblocking canonical catalog."""

        _ = kind
        return None

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Keep legacy cached rows cold so metadata bootstrap is exercised."""

        _ = kind
        return None

    def cached_metadata_snapshot_for_kind(
        self,
        kind: str,
    ) -> ModelCatalogSnapshot | None:
        """Return local metadata rows without backend availability."""

        rows = tuple(item for item in self._items if item.kind == kind)
        return ModelCatalogSnapshot(kind=kind, items=rows, generation=7)


def _rich_choice_resolver(catalog: _FakeModelCatalog) -> RichChoiceResolver:
    """Return a rich choice resolver backed by the fake catalog."""

    return RichChoiceResolver(
        catalog_index=ModelChoiceCatalogIndex(model_catalog=catalog)
    )


def _model_choice_snapshot(
    *,
    field_behavior: FieldBehavior,
    key: str,
    value: object,
    node_name: str = "node",
    node_type: object = "",
    field_type: object = None,
    field_info: object = None,
    catalog: _FakeModelCatalog | None = None,
    resolver: RichChoiceResolver | None = None,
) -> PanelModelChoiceSnapshot:
    """Return a prepared model-choice snapshot for one test field."""

    return PanelModelChoiceSnapshotController(
        model_catalog_service=catalog,
        model_choice_resolver=resolver,
    ).snapshot_for_field(
        PanelModelChoiceSnapshotRequest(
            field_behavior=field_behavior,
            node_name=node_name,
            key=key,
            value=value,
            node_type=node_type,
            field_type=field_type,
            field_info=field_info,
            node_definition_gateway=None,
        )
    )


def test_choice_factory_builds_explicit_model_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit MODEL_PICKER behavior should build a model picker in the new owner."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    thumbnail_repository = cast(ThumbnailAssetRepository, object())
    thumbnail_route_factory = cast(Any, object())
    model_catalog = _FakeModelCatalog(
        (_model_item("checkpoints", "models/base.safetensors", "Base"),)
    )
    field_behavior = FieldBehavior(
        field_key="ckpt_name",
        presentation=FieldPresentation.MODEL_PICKER,
        style={"model_kind": "checkpoints"},
    )

    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent="parent",
            field_behavior=field_behavior,
            node_name="checkpoint",
            key="ckpt_name",
            value="models/base.safetensors",
            field_meta={},
            model_choice_snapshot=_model_choice_snapshot(
                field_behavior=field_behavior,
                key="ckpt_name",
                value="models/base.safetensors",
                node_name="checkpoint",
                catalog=model_catalog,
            ),
            thumbnail_asset_repository=thumbnail_repository,
            thumbnail_preload_route_factory=thumbnail_route_factory,
        )
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.parent == "parent"
    assert widget.resolution.matched_kinds == ("checkpoints",)
    assert widget.thumbnail_asset_repository is thumbnail_repository
    assert widget.thumbnail_preload_route_factory is thumbnail_route_factory
    assert widget.currentText() == "models/base.safetensors"
    assert model_catalog.list_calls == []


def test_choice_factory_explicit_model_picker_requires_prepared_snapshot() -> None:
    """The factory should fail closed when MODEL_PICKER data was not prepared."""

    with pytest.raises(RuntimeError, match="prepared snapshot"):
        ChoiceFieldFactory().build_field_widget(
            ChoiceFieldBuildRequest(
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
            )
        )


def test_model_choice_snapshot_uses_local_metadata_bootstrap_for_thumbnails() -> None:
    """Cold model pickers should enrich first render from local thumbnail metadata."""

    value = "models/base.safetensors"
    catalog = _MetadataBootstrapCatalog(
        (_thumbnail_model_item("checkpoints", value, "Base"),)
    )

    snapshot = _model_choice_snapshot(
        field_behavior=FieldBehavior(field_key="ckpt_name"),
        key="ckpt_name",
        value=value,
        node_type="CheckpointLoaderSimple",
        field_type="LIST",
        field_info=((value,),),
        catalog=catalog,
        resolver=_rich_choice_resolver(catalog),
    )

    assert snapshot.choice_source is not None
    resolution = snapshot.choice_source.current_resolution()
    assert resolution.enriched_count == 1
    assert resolution.items[0].thumbnail_variants
    assert resolution.items[0].thumbnail_variants[0].role == BANNER_THUMBNAIL_ROLE


def test_choice_factory_keeps_cold_model_list_as_model_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Known model LIST fields should not fall back to plain combos while metadata is cold."""

    monkeypatch.setattr(choice_factory, "ModelPickerField", _FakeModelPickerField)
    monkeypatch.setattr(
        choice_factory,
        "ComboBox",
        lambda *_args, **_kwargs: pytest.fail("model field fell back to ComboBox"),
    )
    field_behavior = FieldBehavior(field_key="ckpt_name")

    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent="parent",
            field_behavior=field_behavior,
            node_name="checkpoint",
            key="ckpt_name",
            value="base-a.safetensors",
            field_meta={},
            model_choice_snapshot=_model_choice_snapshot(
                field_behavior=field_behavior,
                node_name="checkpoint",
                key="ckpt_name",
                value="base-a.safetensors",
                node_type="CheckpointLoaderSimple",
                field_type="LIST",
                field_info=[["base-a.safetensors", "base-b.safetensors"], {}],
                catalog=_FakeModelCatalog(()),
                resolver=_rich_choice_resolver(_FakeModelCatalog(())),
            ),
            field_type="LIST",
            node_type="CheckpointLoaderSimple",
            field_info=[["base-a.safetensors", "base-b.safetensors"], {}],
        )
    )

    assert isinstance(widget, _FakeModelPickerField)
    assert widget.resolution.should_use_rich_picker is True
    assert widget.resolution.matched_kinds == ("checkpoints",)
    assert [item.value for item in widget.resolution.items] == [
        "base-a.safetensors",
        "base-b.safetensors",
    ]


def test_choice_factory_builds_linked_sampler_combo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler combos should prepare link choices and parent registration."""

    monkeypatch.setattr(choice_factory, "ComboBox", _FakeComboBox)
    parent = SimpleNamespace(sampler_link_widgets={}, scheduler_link_widgets={})
    node_data: dict[str, object] = {
        "inputs": {},
        "sampler_links": [
            {"from_cube": "A", "from_node": "ksampler", "label": "link:A"}
        ],
        "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
        "cube_alias": "B",
    }

    widget = ChoiceFieldFactory().build_field_widget(
        ChoiceFieldBuildRequest(
            parent=parent,
            field_behavior=FieldBehavior(field_key="sampler_name"),
            node_name="ksampler",
            key="sampler_name",
            value="euler",
            field_meta={"cube_alias": "B", "node_data": node_data},
            field_type="LIST",
            node_type="KSampler",
            node_definition_gateway=_FakeNodeDefinitionGateway(
                {
                    "KSampler": {
                        "KSampler": {
                            "input": {"required": {"sampler_name": [["euler", "heun"]]}}
                        }
                    }
                }
            ),
        )
    )

    assert isinstance(widget, _FakeComboBox)
    assert widget.current_text == "link:A"
    assert parent.sampler_link_widgets[("B", "ksampler")] is widget
    assert getattr(widget, "_editor_choice_values_by_label")["heun"] == "heun"
    assert getattr(widget, "_editor_choice_values_by_label")["link:A"] == {
        "from_cube": "A",
        "from_node": "ksampler",
    }
    widget.currentTextChanged.emit("heun")
    assert node_data["inputs"] == {}
    assert node_data["sampler_link"] == {"from_cube": "A", "from_node": "ksampler"}
