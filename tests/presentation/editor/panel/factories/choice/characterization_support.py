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

"""Provide local model-choice and combo doubles for factory contracts."""

from __future__ import annotations

from __future__ import annotations
from typing import Any, Callable, cast

from PySide6.QtWidgets import QWidget
from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogSnapshot,
    ModelChoiceCatalogIndex,
    ModelThumbnailVariant,
    RichChoiceResolver,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardCatalogGateway,
)
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
        self._slots: list[Callable[..., None]] = []

    def connect(self, slot: Callable[..., None]) -> None:
        """Register a callback."""
        self._slots.append(slot)

    def emit(self, *args: object) -> None:
        """Emit to all callbacks."""
        for slot in list(self._slots):
            slot(*args)


class _FakeComboBox:
    """ComboBox test double for list widget factories."""

    def __init__(self, _parent: object | None = None) -> None:
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

    def reconcile_choice_items(
        self,
        items: object,
        selected_label: str,
    ) -> None:
        """Record one prepared editor-choice replacement."""

        prepared = list(cast(list[tuple[str, object]], items))
        self.addItems([label for label, _value in prepared])
        self.current_text = selected_label
        self._editor_choice_values_by_label = dict(prepared)


class _FakeChoiceParent:
    """Expose the two choice-link registries observed by the factory."""

    def __init__(self) -> None:
        """Create empty per-parent sampler and scheduler registries."""

        self.sampler_link_widgets: dict[tuple[object, str], _FakeComboBox] = {}
        self.scheduler_link_widgets: dict[tuple[object, str], _FakeComboBox] = {}


def as_choice_parent(parent: _FakeChoiceParent) -> QWidget:
    """Adapt the typed fake parent to the Qt boundary consumed by the factory."""

    return cast(QWidget, parent)


class _FakeModelPickerField:
    """ModelPickerField test double that records constructor inputs."""

    def __init__(
        self,
        parent: object | None = None,
        *,
        choice_source: Any,
        thumbnail_asset_repository: object | None = None,
        current_value: str = "",
        search_placeholder: str = "Search models",
        metadata_action_handler: object | None = None,
        thumbnail_preload_route_factory: object | None = None,
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


class _FakePromptAutocompleteGateway:
    """Return empty autocomplete results for focused factory tests."""

    @staticmethod
    def search(
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        _ = (prefix, limit)
        return ()


def _wildcard_gateway() -> PromptWildcardCatalogGateway:
    """Return an opaque wildcard gateway at the external protocol boundary."""

    return cast(PromptWildcardCatalogGateway, object())
