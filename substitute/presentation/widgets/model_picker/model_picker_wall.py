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

"""Adapt reusable model picker rows to the generic media wall widget."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QWidget

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from substitute.presentation.widgets.media_wall import (
    MediaWallItem,
    MediaWallThumbnailCache,
    MediaWallThumbnailPreloader,
    MediaWallView,
    PickerJustifiedWallProfile,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
    ModelMetadataContextMenuPresenter,
    ModelMetadataContextMenuTarget,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
)

MODEL_PICKER_WALL_PROFILE = PickerJustifiedWallProfile(
    target_row_height=198.0,
    min_row_height=156.0,
    max_row_height=258.0,
    minimum_tile_width=126.0,
)


class ModelPickerWallView(MediaWallView):
    """Render reusable model picker items through the justified media wall."""

    modelActivated = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        asset_repository: ThumbnailAssetRepository | None = None,
        thumbnail_cache: MediaWallThumbnailCache | None = None,
        thumbnail_preloader: MediaWallThumbnailPreloader | None = None,
        open_url: UrlOpener | None = None,
        metadata_action_handler: ModelMetadataContextActionHandler | None = None,
    ) -> None:
        """Initialize the model media wall with the shared picker profile."""

        super().__init__(
            parent,
            asset_repository=asset_repository,
            thumbnail_cache=thumbnail_cache,
            thumbnail_preloader=thumbnail_preloader,
            profile=MODEL_PICKER_WALL_PROFILE,
        )
        self._picker_items: tuple[ModelPickerItem, ...] = ()
        self._open_url = open_url or open_external_url
        self._metadata_context_menu = ModelMetadataContextMenuPresenter(
            parent=self,
            open_url=self._open_url,
            action_handler=metadata_action_handler,
        )
        self.itemActivated.connect(self._activate_model)
        self.itemContextMenuRequested.connect(self._show_model_context_menu)

    def set_picker_items(self, items: Iterable[ModelPickerItem]) -> None:
        """Replace the model picker items rendered by this wall."""

        self._picker_items = tuple(items)
        self.set_items(wall_items_for_model_picker_items(self._picker_items))

    def picker_items(self) -> tuple[ModelPickerItem, ...]:
        """Return the model picker items currently rendered by this wall."""

        return self._picker_items

    def current_model_item(self) -> ModelPickerItem | None:
        """Return the current keyboard-selected model picker item."""

        payload = self.current_payload()
        if not isinstance(payload, ModelPickerItem):
            return None
        return payload

    def _activate_model(self, item: object) -> None:
        """Emit strongly named activation for picker item payloads."""

        if isinstance(item, ModelPickerItem):
            self.modelActivated.emit(item)

    def _show_model_context_menu(self, item: object, global_pos: QPoint) -> None:
        """Show metadata actions for the requested picker item."""

        target = self._metadata_context_menu_target(item)
        if target is None:
            return
        self._metadata_context_menu.show_menu(target, global_pos)

    def _metadata_context_menu_target(
        self,
        item: object,
    ) -> ModelMetadataContextMenuTarget | None:
        """Return a shared metadata context-menu target for picker items."""

        if not isinstance(item, ModelPickerItem):
            return None
        return ModelMetadataContextMenuTarget(
            title=item.title,
            subtitle=item.subtitle,
            backend_value=item.backend_value,
            relative_path=item.relative_path,
            model_kind=item.model_kind,
            model_page_url=item.model_page_url,
        )


def wall_items_for_model_picker_items(
    items: tuple[ModelPickerItem, ...],
) -> tuple[MediaWallItem, ...]:
    """Convert model picker items into generic media wall items."""

    return tuple(
        MediaWallItem(
            item_id=item.item_id,
            title=item.title,
            subtitle=item.subtitle,
            aspect_ratio=item.aspect_ratio,
            thumbnail_variants=item.thumbnail_variants,
            payload=item,
            tooltip=item.relative_path,
        )
        for item in items
    )


__all__ = [
    "MODEL_PICKER_WALL_PROFILE",
    "ModelPickerWallView",
    "wall_items_for_model_picker_items",
]
