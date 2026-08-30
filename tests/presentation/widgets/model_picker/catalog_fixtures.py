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

"""Provide model catalog values and boundary fakes for picker tests."""

from __future__ import annotations

from uuid import UUID


from PySide6.QtGui import QColor, QImage

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelMetadataRefreshEvent,
    ModelThumbnailVariant,
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextMenuTarget,
)
from substitute.shared.qt_thumbnail_codec import prepare_qt_thumbnail


class _FakeModelCatalog:
    """Return deterministic model picker catalog rows."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store fake catalog rows for list and refresh calls."""

        self.items = items
        self.list_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return fake rows and record the requested kind."""

        self.list_calls.append(kind)
        return self.items

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return fake rows and record the requested kind."""

        self.refresh_calls.append(kind)
        return self.items

    def current_resolution(self) -> RichChoiceResolution:
        """Return fake rows as a rich-choice source resolution."""

        return _rich_choice_resolution_from_catalog_items(self.items)

    def refresh(self) -> RichChoiceResolution:
        """Record a picker refresh and return fake rich-choice rows."""

        self.refresh_calls.append("checkpoints")
        return self.current_resolution()

    def invalidate(self, kind: str | None = None) -> None:
        """Ignore invalidation because tests control fake catalog rows directly."""

        _ = kind


class _ClearRecorder:
    """Record thumbnail cache clear calls for picker event tests."""

    def __init__(self) -> None:
        """Create an empty clear-call recorder."""

        self.calls = 0

    def clear(self) -> None:
        """Record one cache clear."""

        self.calls += 1


class _FakeStaleChoiceSource:
    """Return stale Comfy choices plus one metadata-backed downloaded model."""

    def __init__(
        self,
        *,
        choices: tuple[ModelCatalogItem, ...],
        extra: ModelCatalogItem,
    ) -> None:
        """Store the exact choices and a selected value absent from those choices."""

        self._choices = choices
        self._extra = extra

    def current_resolution(self) -> RichChoiceResolution:
        """Return the stale Comfy choices."""

        return _rich_choice_resolution_from_catalog_items(self._choices)

    def refresh(self) -> RichChoiceResolution:
        """Return the stale Comfy choices."""

        return self.current_resolution()

    def extra_item_for_value(self, value: str) -> RichChoiceItem | None:
        """Return metadata for the downloaded model when selected."""

        if value == self._extra.backend_value:
            return _rich_choice_item(self._extra)
        return None


class _FailingRefreshChoiceSource:
    """Return initial choices but fail when the picker asks Backend for freshness."""

    def __init__(self, items: tuple[ModelCatalogItem, ...]) -> None:
        """Store initial items and refresh attempts."""

        self._items = items
        self.refresh_calls = 0

    def current_resolution(self) -> RichChoiceResolution:
        """Return the initial rich-choice resolution."""

        return _rich_choice_resolution_from_catalog_items(self._items)

    def refresh(self) -> RichChoiceResolution:
        """Raise to simulate unavailable Backend model selection."""

        self.refresh_calls += 1
        raise RuntimeError("backend unavailable")


class _ThumbnailAssetRepository:
    """Return configured thumbnail assets and count reads by storage key."""

    def __init__(self, assets: dict[str, ThumbnailAsset]) -> None:
        """Store thumbnail assets for model picker field tests."""

        self._assets = assets
        self.reads_by_key: dict[str, int] = {}

    def read_thumbnail_asset(self, storage_key: str) -> ThumbnailAsset | None:
        """Record and return one configured thumbnail asset."""

        self.reads_by_key[storage_key] = self.reads_by_key.get(storage_key, 0) + 1
        return self._assets.get(storage_key)


class _MetadataActionHandler:
    """Record model metadata menu action targets in field tests."""

    def __init__(self) -> None:
        """Prepare refresh observations."""

        self.refresh_targets: list[object] = []

    def refresh_civitai_metadata(self, target: object) -> None:
        """Record one refresh target."""

        self.refresh_targets.append(target)

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return no output choices for existing field tests."""

        return ()

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return no active output choice for existing field tests."""

        return None

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Ignore output thumbnail requests in existing field tests."""

        _ = (target, image_id)


def _rich_choice_resolution_from_catalog_items(
    items: tuple[ModelCatalogItem, ...],
) -> RichChoiceResolution:
    """Adapt fake catalog items into a rich-choice resolution for widget tests."""

    rich_items = tuple(_rich_choice_item(item) for item in items)
    matched_kinds = tuple(sorted({item.kind for item in items}))
    return RichChoiceResolution(
        items=rich_items,
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=len(rich_items),
        enriched_count=len(rich_items),
        ambiguous_count=0,
        unmatched_count=0,
        reason="test fixture",
    )


def _metadata_event(
    kind: str,
    value: str,
    *,
    thumbnail_updated: bool = True,
) -> ModelMetadataRefreshEvent:
    """Return one model metadata event for picker refresh tests."""

    return ModelMetadataRefreshEvent(
        kind=kind,
        value=value,
        relative_path=value,
        sha256="ABC123",
        provider_status="found",
        thumbnail_updated=thumbnail_updated,
    )


def _rich_choice_item(item: ModelCatalogItem) -> RichChoiceItem:
    """Adapt one fake catalog item into a rich choice item."""

    return RichChoiceItem(
        value=item.backend_value,
        title=item.display_name or item.basename,
        subtitle=item.display_subtitle,
        search_text=item.search_text,
        model_kind=item.kind,
        catalog_item=item,
        thumbnail_variants=item.thumbnail_variants,
        is_enriched=True,
        is_ambiguous=False,
    )


def _item(
    backend_value: str,
    display_name: str,
    display_subtitle: str | None,
    *,
    folder: str = "models",
    thumbnail_variants: tuple[ModelThumbnailVariant, ...] = (),
    model_page_url: str | None = None,
) -> ModelCatalogItem:
    """Return one generic catalog item for field tests."""

    return ModelCatalogItem(
        kind="checkpoints",
        display_name=display_name,
        display_subtitle=display_subtitle,
        backend_value=backend_value,
        relative_path=backend_value,
        folder=folder,
        basename=backend_value.rsplit("/", 1)[-1].removesuffix(".safetensors"),
        extension=".safetensors",
        thumbnail_variants=thumbnail_variants,
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=model_page_url,
        collision_key=backend_value.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=f"{display_name} {backend_value}".casefold(),
    )


def _thumbnail_variant(storage_key: str, *, role: str) -> ModelThumbnailVariant:
    """Return one prepared model thumbnail variant."""

    return ModelThumbnailVariant(
        size=768,
        storage_key=storage_key,
        width=768,
        height=160,
        content_format="sqthumb-qimage-argb32-premultiplied",
        byte_size=768 * 160 * 4,
        role=role,
    )


def _thumbnail_asset(storage_key: str, color: QColor) -> ThumbnailAsset:
    """Return one Qt-ready thumbnail asset for field tests."""

    image = QImage(768, 160, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    prepared = prepare_qt_thumbnail(image)
    return ThumbnailAsset(
        storage_key=storage_key,
        width=prepared.width,
        height=prepared.height,
        qt_format=prepared.qt_format,
        bytes_per_line=prepared.bytes_per_line,
        content_format=prepared.content_format,
        payload=prepared.payload,
    )
