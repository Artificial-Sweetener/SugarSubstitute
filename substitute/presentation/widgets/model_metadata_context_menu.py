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

"""Build shared context menus for model metadata-backed UI entries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    Action,
    RoundMenu,
)

from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    OutputCanvasThumbnailChoice,
)

from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    civitai_page_action,
    open_external_url,
)
from substitute.presentation.widgets.menu_model import (
    LazyMenuSubmenu,
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer

_SET_THUMBNAIL_FROM_CANVAS_LABEL = "Set thumbnail from canvas"


class ModelMetadataContextActionHandler(Protocol):
    """Handle commands requested from a model metadata context menu."""

    def refresh_civitai_metadata(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> None:
        """Schedule a manual CivitAI metadata refresh for the target model."""

    def output_canvas_thumbnail_choices(
        self,
    ) -> tuple[OutputCanvasThumbnailChoice, ...]:
        """Return selectable final output images for thumbnail assignment."""

    def active_output_canvas_thumbnail_choice(
        self,
    ) -> OutputCanvasThumbnailChoice | None:
        """Return the active final output image for thumbnail assignment."""

    def set_thumbnail_from_output_image(
        self,
        target: ModelMetadataContextMenuTarget,
        image_id: UUID,
    ) -> None:
        """Schedule assigning one output image as the target model thumbnail."""


@dataclass(frozen=True, slots=True)
class ModelMetadataContextMenuTarget:
    """Describe one model-like metadata row targeted by a context menu."""

    title: str
    subtitle: str | None = None
    backend_value: str | None = None
    relative_path: str | None = None
    model_kind: str | None = None
    model_page_url: str | None = None
    trained_words: tuple[str, ...] = ()

    def display_label(self) -> str:
        """Return a compact human label for action text and diagnostics."""

        title = self.title.strip()
        subtitle = "" if self.subtitle is None else self.subtitle.strip()
        if title and subtitle:
            return f"{title} - {subtitle}"
        return title


@dataclass(frozen=True, slots=True)
class ModelMetadataMenuAction:
    """Describe one executable model metadata menu item."""

    label: str
    callback: Callable[[], None]
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ModelMetadataMenuSubmenu:
    """Describe one nested model metadata menu item."""

    label: str
    children: tuple[ModelMetadataMenuItem, ...]
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ModelMetadataMenuSeparator:
    """Describe a separator between model metadata menu groups."""


ModelMetadataMenuItem = (
    ModelMetadataMenuAction | ModelMetadataMenuSubmenu | ModelMetadataMenuSeparator
)


class ModelMetadataContextMenuActionBuilder:
    """Build shared menu items for a model metadata context-menu target."""

    def __init__(
        self,
        *,
        open_url: UrlOpener | None = None,
        action_handler: ModelMetadataContextActionHandler | None = None,
    ) -> None:
        """Store collaborators used by shared metadata actions."""

        self._open_url = open_url or open_external_url
        self._action_handler = action_handler

    def menu_items_for_target(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> tuple[ModelMetadataMenuItem, ...]:
        """Return all currently available menu items for one metadata target."""

        items: list[ModelMetadataMenuItem] = []
        page_action = self.civitai_page_action_for_target(target)
        if page_action is not None:
            items.append(page_action)
        refresh_action = self.refresh_metadata_action_for_target(target)
        if refresh_action is not None:
            items.append(refresh_action)
        thumbnail_action = self.output_thumbnail_action_for_target(target)
        if thumbnail_action is not None:
            items.append(thumbnail_action)
        return tuple(items)

    def civitai_page_action_for_target(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> ModelMetadataMenuAction | None:
        """Return the shared CivitAI page action for one metadata target."""

        action = civitai_page_action(target.model_page_url, self._open_url)
        if action is None:
            return None

        def open_page(action: Action = action) -> None:
            """Trigger the prepared CivitAI page action."""

            action.trigger()

        return ModelMetadataMenuAction(
            action.text(),
            open_page,
        )

    def refresh_metadata_action_for_target(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> ModelMetadataMenuAction | None:
        """Return the shared manual metadata refresh action for one target."""

        if self._action_handler is None or not _target_can_refresh_metadata(target):
            return None

        def refresh_metadata(target: ModelMetadataContextMenuTarget = target) -> None:
            """Schedule metadata refresh for the captured target."""

            assert self._action_handler is not None
            self._action_handler.refresh_civitai_metadata(target)

        return ModelMetadataMenuAction(
            "Refresh CivitAI metadata",
            refresh_metadata,
        )

    def output_thumbnail_action_for_target(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> ModelMetadataMenuItem | None:
        """Return the adaptive output-canvas thumbnail action for one target."""

        if self._action_handler is None or not _target_can_refresh_metadata(target):
            return None
        choices = self._action_handler.output_canvas_thumbnail_choices()
        active_choice = self._action_handler.active_output_canvas_thumbnail_choice()
        return _output_thumbnail_menu_item(
            target=target,
            choices=choices,
            active_choice=active_choice,
            action_handler=self._action_handler,
        )


class ModelMetadataContextMenuPresenter:
    """Present model metadata context menus through one shared menu builder."""

    def __init__(
        self,
        *,
        parent: QWidget,
        open_url: UrlOpener | None = None,
        action_handler: ModelMetadataContextActionHandler | None = None,
        action_builder: ModelMetadataContextMenuActionBuilder | None = None,
    ) -> None:
        """Bind a Qt parent and action builder for future menu openings."""

        self._parent = parent
        self._action_builder = action_builder or ModelMetadataContextMenuActionBuilder(
            open_url=open_url,
            action_handler=action_handler,
        )

    def menu_items_for_target(
        self,
        target: ModelMetadataContextMenuTarget,
    ) -> tuple[ModelMetadataMenuItem, ...]:
        """Return menu items without presenting a menu."""

        return self._action_builder.menu_items_for_target(target)

    def show_menu(
        self,
        target: ModelMetadataContextMenuTarget,
        global_pos: QPoint,
    ) -> bool:
        """Show the metadata context menu and return whether it had actions."""

        items = self.menu_items_for_target(target)
        if not items:
            return False
        menu = QFluentMenuRenderer(parent=self._parent).render(
            MenuModel(entries=model_metadata_menu_entries(items))
        )
        menu.exec(global_pos)
        return True


def populate_model_metadata_menu(
    menu: RoundMenu,
    items: tuple[ModelMetadataMenuItem, ...],
) -> None:
    """Populate a qfluent menu from shared model metadata menu items."""

    parent = menu.parent()
    renderer_parent = parent if isinstance(parent, QWidget) else menu
    QFluentMenuRenderer(parent=renderer_parent).populate_menu(
        menu,
        model_metadata_menu_entries(items),
    )


def model_metadata_menu_entries(
    items: tuple[ModelMetadataMenuItem, ...],
) -> tuple[MenuEntry, ...]:
    """Return shared renderer menu entries for metadata menu items."""

    entries: list[MenuEntry] = []
    for index, item in enumerate(items):
        if isinstance(item, ModelMetadataMenuAction):
            entries.append(
                MenuItem(
                    action_id=f"model_metadata.action.{index}",
                    label=item.label,
                    callback=item.callback,
                    enabled=item.enabled,
                )
            )
        elif isinstance(item, ModelMetadataMenuSeparator):
            entries.append(MenuSeparator())
        elif isinstance(item, ModelMetadataMenuSubmenu):
            entries.append(
                LazyMenuSubmenu(
                    item.label,
                    entries_factory=_metadata_submenu_entries_factory(item.children),
                    enabled=item.enabled and _has_enabled_action(item.children),
                )
            )
    return tuple(entries)


def _metadata_submenu_entries_factory(
    children: tuple[ModelMetadataMenuItem, ...],
) -> Callable[[], tuple[MenuEntry, ...]]:
    """Return a typed lazy-entry factory for metadata submenu children."""

    return lambda: model_metadata_menu_entries(children)


def _has_enabled_action(items: tuple[ModelMetadataMenuItem, ...]) -> bool:
    """Return whether a menu tree contains at least one enabled action."""

    for item in items:
        if isinstance(item, ModelMetadataMenuAction) and item.enabled:
            return True
        if isinstance(item, ModelMetadataMenuSubmenu) and _has_enabled_action(
            item.children
        ):
            return True
    return False


def _target_can_refresh_metadata(target: ModelMetadataContextMenuTarget) -> bool:
    """Return whether one target has enough local identity to refresh metadata."""

    return bool(
        (target.model_kind or "").strip() and (target.backend_value or "").strip()
    )


def _output_thumbnail_menu_item(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    active_choice: OutputCanvasThumbnailChoice | None,
    action_handler: ModelMetadataContextActionHandler,
) -> ModelMetadataMenuItem:
    """Return the simplest output-canvas thumbnail menu item for the choices."""

    if not choices:
        return ModelMetadataMenuAction(
            _SET_THUMBNAIL_FROM_CANVAS_LABEL,
            lambda: None,
            enabled=False,
        )
    if len(choices) == 1:
        return _thumbnail_choice_action(
            _SET_THUMBNAIL_FROM_CANVAS_LABEL,
            target,
            choices[0],
            action_handler,
        )
    children = _thumbnail_submenu_children(
        target=target,
        choices=choices,
        active_choice=active_choice,
        action_handler=action_handler,
    )
    return ModelMetadataMenuSubmenu(_SET_THUMBNAIL_FROM_CANVAS_LABEL, children)


def _thumbnail_submenu_children(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    active_choice: OutputCanvasThumbnailChoice | None,
    action_handler: ModelMetadataContextActionHandler,
) -> tuple[ModelMetadataMenuItem, ...]:
    """Return submenu children following the output canvas hierarchy."""

    children: list[ModelMetadataMenuItem] = []
    if active_choice is not None:
        children.append(
            _thumbnail_choice_action(
                "Current image",
                target,
                active_choice,
                action_handler,
            )
        )
        children.append(ModelMetadataMenuSeparator())
    children.extend(
        _output_canvas_hierarchy_items(
            target=target,
            choices=choices,
            action_handler=action_handler,
        )
    )
    return tuple(children)


def _thumbnail_choice_action(
    label: str,
    target: ModelMetadataContextMenuTarget,
    choice: OutputCanvasThumbnailChoice,
    action_handler: ModelMetadataContextActionHandler,
) -> ModelMetadataMenuAction:
    """Return one leaf action for assigning a selected output image."""

    def set_thumbnail(
        target: ModelMetadataContextMenuTarget = target,
        image_id: UUID = choice.image_id,
    ) -> None:
        """Schedule thumbnail assignment for the captured output image."""

        action_handler.set_thumbnail_from_output_image(target, image_id)

    return ModelMetadataMenuAction(
        label,
        set_thumbnail,
    )


def _output_canvas_hierarchy_items(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    action_handler: ModelMetadataContextActionHandler,
) -> tuple[ModelMetadataMenuItem, ...]:
    """Return the canonical output canvas menu tree for choices."""

    if _has_meaningful_scenes(choices):
        return _scene_level_items(
            target=target,
            choices=choices,
            action_handler=action_handler,
        )
    return _batch_or_source_level_items(
        target=target,
        choices=choices,
        action_handler=action_handler,
    )


def _scene_level_items(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    action_handler: ModelMetadataContextActionHandler,
) -> tuple[ModelMetadataMenuItem, ...]:
    """Return scene menu items, each containing that scene's canvas tree."""

    items: list[ModelMetadataMenuItem] = []
    for scene_choices in _groups_by_scene(choices):
        scene_label = scene_choices[0].scene_title or "Scene"
        if len(scene_choices) == 1:
            items.append(
                _thumbnail_choice_action(
                    scene_label,
                    target,
                    scene_choices[0],
                    action_handler,
                )
            )
        else:
            items.append(
                ModelMetadataMenuSubmenu(
                    scene_label,
                    _batch_or_source_level_items(
                        target=target,
                        choices=scene_choices,
                        action_handler=action_handler,
                    ),
                )
            )
    return tuple(items)


def _batch_or_source_level_items(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    action_handler: ModelMetadataContextActionHandler,
) -> tuple[ModelMetadataMenuItem, ...]:
    """Return batch items when batches exist, otherwise source items."""

    set_indices = sorted({choice.set_index for choice in choices})
    if len(set_indices) <= 1:
        return _source_level_items(
            target=target,
            choices=choices,
            action_handler=action_handler,
        )

    items: list[ModelMetadataMenuItem] = []
    for set_index in set_indices:
        batch_choices = tuple(
            choice for choice in choices if choice.set_index == set_index
        )
        if len(batch_choices) == 1:
            items.append(
                _thumbnail_choice_action(
                    _batch_label(set_index),
                    target,
                    batch_choices[0],
                    action_handler,
                )
            )
            continue
        items.append(
            ModelMetadataMenuSubmenu(
                _batch_label(set_index),
                _source_level_items(
                    target=target,
                    choices=batch_choices,
                    action_handler=action_handler,
                ),
            )
        )
    return tuple(items)


def _source_level_items(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    action_handler: ModelMetadataContextActionHandler,
) -> tuple[ModelMetadataMenuItem, ...]:
    """Return cube-output items for one scene/batch scope."""

    items: list[ModelMetadataMenuItem] = []
    for source_key in dict.fromkeys(choice.source_key for choice in choices):
        source_choices = tuple(
            choice for choice in choices if choice.source_key == source_key
        )
        source_label = source_choices[0].source_label or "Output"
        if len(source_choices) == 1:
            items.append(
                _thumbnail_choice_action(
                    source_label,
                    target,
                    source_choices[0],
                    action_handler,
                )
            )
            continue
        items.append(
            ModelMetadataMenuSubmenu(
                source_label,
                _image_leaf_actions_for_choices(
                    target=target,
                    choices=source_choices,
                    action_handler=action_handler,
                ),
            )
        )
    return tuple(items)


def _image_leaf_actions_for_choices(
    *,
    target: ModelMetadataContextMenuTarget,
    choices: tuple[OutputCanvasThumbnailChoice, ...],
    action_handler: ModelMetadataContextActionHandler,
) -> tuple[ModelMetadataMenuAction, ...]:
    """Return concrete image leaves under one cube output."""

    return tuple(
        _thumbnail_choice_action(
            f"Image {index}",
            target,
            choice,
            action_handler,
        )
        for index, choice in enumerate(choices, start=1)
    )


def _groups_by_scene(
    choices: tuple[OutputCanvasThumbnailChoice, ...],
) -> tuple[tuple[OutputCanvasThumbnailChoice, ...], ...]:
    """Return choices grouped by deterministic scene identity."""

    sorted_choices = sorted(
        choices,
        key=lambda choice: (choice.scene_order, choice.scene_title, choice.scene_key),
    )
    groups: list[tuple[OutputCanvasThumbnailChoice, ...]] = []
    for scene_key in dict.fromkeys(choice.scene_key for choice in sorted_choices):
        groups.append(
            tuple(choice for choice in sorted_choices if choice.scene_key == scene_key)
        )
    return tuple(groups)


def _has_meaningful_scenes(
    choices: tuple[OutputCanvasThumbnailChoice, ...],
) -> bool:
    """Return whether choices contain useful scene grouping metadata."""

    scene_keys = {choice.scene_key for choice in choices if choice.scene_key}
    if len(scene_keys) > 1:
        return True
    if not scene_keys:
        return False
    return any(
        choice.scene_title and choice.scene_title != "Scene" for choice in choices
    )


def _batch_label(set_index: int) -> str:
    """Return user-facing batch text for one output set index."""

    return f"Batch {set_index}"


__all__ = [
    "ModelMetadataContextActionHandler",
    "ModelMetadataContextMenuActionBuilder",
    "ModelMetadataContextMenuPresenter",
    "ModelMetadataContextMenuTarget",
    "ModelMetadataMenuAction",
    "ModelMetadataMenuItem",
    "ModelMetadataMenuSeparator",
    "ModelMetadataMenuSubmenu",
    "model_metadata_menu_entries",
    "populate_model_metadata_menu",
]
