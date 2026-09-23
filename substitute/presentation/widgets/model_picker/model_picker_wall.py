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

from collections.abc import Callable, Iterable

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.model_metadata import ThumbnailAssetRepository
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.model_updates.icon_menu import show_update_icon_menu
from substitute.presentation.resources.fluent_app_icon import AppIcon
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
        metadata_target_updated: Callable[[], None] | None = None,
        thumbnail_library_opening: Callable[[], None] | None = None,
        model_updates: ModelUpdatePickerBridge | None = None,
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
        self._model_updates = model_updates
        self._metadata_context_menu = ModelMetadataContextMenuPresenter(
            parent=self,
            open_url=self._open_url,
            action_handler=metadata_action_handler,
            target_updated=metadata_target_updated,
            thumbnail_library_opening=thumbnail_library_opening,
            model_updates=model_updates,
        )
        self.itemActivated.connect(self._activate_model)
        self.itemBadgeActivated.connect(self._activate_update)
        self.itemBadgeContextMenuRequested.connect(self._show_update_icon_menu)
        self.itemContextMenuRequested.connect(self._show_model_context_menu)
        if model_updates is not None:
            model_updates.changed.connect(self._refresh_update_indicators)

    def set_picker_items(self, items: Iterable[ModelPickerItem]) -> None:
        """Replace the model picker items rendered by this wall."""

        self._picker_items = tuple(items)
        self._refresh_update_indicators()

    def _refresh_update_indicators(self) -> None:
        """Reproject one authoritative update state over the visible tiles."""

        self.set_items(
            wall_items_for_model_picker_items(
                self._picker_items, model_updates=self._model_updates
            )
        )

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

    def _activate_update(self, item: object) -> None:
        """Open history without selecting the tile's backend model value."""

        if isinstance(item, ModelPickerItem) and self._model_updates is not None:
            self._model_updates.request_family(item.sha256)

    def _show_update_icon_menu(self, item: object, global_pos: QPoint) -> None:
        """Right-clicking a tile badge offers only update-specific choices."""

        if isinstance(item, ModelPickerItem) and self._model_updates is not None:
            show_update_icon_menu(
                parent=self,
                updates=self._model_updates,
                sha256=item.sha256,
                global_pos=global_pos,
            )

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
            provider_links=item.provider_links,
            sha256=item.sha256,
        )


def wall_items_for_model_picker_items(
    items: tuple[ModelPickerItem, ...],
    *,
    model_updates: ModelUpdatePickerBridge | None = None,
) -> tuple[MediaWallItem, ...]:
    """Convert model picker items into generic media wall items."""

    badge_icon = AppIcon.ARROW_CIRCLE_UP_SPARKLE_20_REGULAR.qicon()
    badge_tooltip = render_application_text(
        app_text("Update available — view versions")
    )
    return tuple(
        MediaWallItem(
            item_id=item.item_id,
            title=item.title,
            subtitle=item.subtitle,
            aspect_ratio=item.aspect_ratio,
            thumbnail_variants=item.thumbnail_variants,
            payload=item,
            tooltip=item.relative_path,
            corner_badge_icon=(
                badge_icon
                if model_updates is not None
                and model_updates.proposal_for_sha(item.sha256) is not None
                else None
            ),
            corner_badge_tooltip=badge_tooltip,
        )
        for item in items
    )


__all__ = [
    "MODEL_PICKER_WALL_PROFILE",
    "ModelPickerWallView",
    "wall_items_for_model_picker_items",
]
