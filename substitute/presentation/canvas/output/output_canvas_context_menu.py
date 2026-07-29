#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Render the existing Output canvas context menu from document-backed state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtWidgets import QWidget
from cutecanvas import CanvasContentReference
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    MenuAnimationType,
)
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_resolution import (
    output_compare_available,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.menu_icons import transparent_menu_icon
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer


@dataclass(frozen=True, slots=True, weakref_slot=True)
class OutputCanvasContextMenu:
    """Own the established Output canvas actions for non-grid presentations."""

    parent: QWidget
    current_image_id: Callable[[], UUID | None]
    content_reference_for: Callable[[UUID], CanvasContentReference | None]
    image_payload: Callable[[UUID], object | None]
    image_metadata: Callable[[UUID], OutputImageMeta | None]
    projection: Callable[[], OutputCanvasProjection | None]
    image_is_authorized: Callable[[UUID], bool]
    compare_enabled: Callable[[], bool]
    set_compare_enabled: Callable[[bool], None]
    active_scene_overview: Callable[[], bool]
    active_set_index: Callable[[], int]
    request_copy: Callable[[CanvasContentReference], None]
    open_single_editor: Callable[[object, OutputImageMeta], bool] | None
    open_all_editor: Callable[[list[tuple[object, OutputImageMeta]]], bool] | None
    reveal_asset: Callable[[OutputImageMeta], bool] | None
    canvas_detached: Callable[[], bool]
    request_dock_action: Callable[[], None]

    def show(self, global_position: object) -> None:
        """Show the established Output menu when the current route permits it."""

        model = self.menu_model()
        if model is None:
            return
        menu = QFluentMenuRenderer(parent=self.parent).render(model)
        menu.exec(global_position, aniType=MenuAnimationType.DROP_DOWN)

    def menu_model(self) -> MenuModel | None:
        """Build the existing Output action set for the active authorized route."""

        compare_enabled = self.compare_enabled()
        if not compare_enabled and (
            self.active_scene_overview() or self.active_set_index() == 0
        ):
            return None
        return MenuModel(entries=self._entries(compare_enabled))

    def copy_current_image(self) -> None:
        """Copy the authorized current image using the shared MIME policy."""

        image_id = self.current_image_id()
        if image_id is None or not self.image_is_authorized(image_id):
            return
        reference = self.content_reference_for(image_id)
        if reference is not None:
            self.request_copy(reference)

    def open_current_external(self) -> None:
        """Open the authorized current output in the configured external editor."""

        opener = self.open_single_editor
        image_id = self.current_image_id()
        if opener is None or image_id is None or not self.image_is_authorized(image_id):
            return
        image = self.image_payload(image_id)
        metadata = self.image_metadata(image_id)
        if image is not None and metadata is not None:
            opener(image, metadata)

    def open_all_external(self) -> None:
        """Open every authorized current-projection output in the external editor."""

        opener = self.open_all_editor
        if opener is None:
            return
        images = [
            (image, metadata)
            for image_id in self._projection_image_ids()
            if self.image_is_authorized(image_id)
            for image in (self.image_payload(image_id),)
            for metadata in (self.image_metadata(image_id),)
            if image is not None and metadata is not None
        ]
        if images:
            opener(images)

    def reveal_current_asset(self) -> None:
        """Reveal the authorized current output when it has a local asset path."""

        reveal = self.reveal_asset
        image_id = self.current_image_id()
        if reveal is None or image_id is None or not self.image_is_authorized(image_id):
            return
        metadata = self.image_metadata(image_id)
        if metadata is not None and metadata.path.strip():
            reveal(metadata)

    def _entries(self, compare_enabled: bool) -> tuple[MenuEntry, ...]:
        """Build one complete Output menu without changing route state."""

        entries: list[MenuEntry] = []
        compare = self._compare_item(compare_enabled)
        if compare is not None:
            entries.extend((compare, MenuSeparator()))
        entries.extend(
            (
                MenuItem(
                    "output_canvas.copy",
                    app_text("Copy"),
                    callback=self.copy_current_image,
                    icon=FIF.COPY,
                ),
                MenuItem(
                    "output_canvas.open_current_external",
                    app_text("Open in Photoshop"),
                    callback=self.open_current_external,
                    icon=FIF.PHOTO,
                ),
                MenuItem(
                    "output_canvas.open_all_external",
                    app_text("Open All in Photoshop"),
                    callback=self.open_all_external,
                    icon=AppIcon.IMAGE_MULTIPLE_20_REGULAR,
                ),
                MenuItem(
                    "output_canvas.reveal_current_asset",
                    app_text("Reveal in File Manager"),
                    callback=self.reveal_current_asset,
                    enabled=self._current_asset_has_path(),
                    icon=AppIcon.FOLDER_OPEN_20_REGULAR,
                ),
                MenuSeparator(),
                MenuItem(
                    "output_canvas.dock_action",
                    app_text(
                        "Redock canvas" if self.canvas_detached() else "Undock canvas"
                    ),
                    callback=self.request_dock_action,
                    icon=(
                        FIF.BACK_TO_WINDOW
                        if self.canvas_detached()
                        else FIF.FULL_SCREEN
                    ),
                ),
            )
        )
        return tuple(entries)

    def _compare_item(self, compare_enabled: bool) -> MenuItem | None:
        """Return the established compare toggle when the projection supports it."""

        projection = self.projection()
        if projection is None or not output_compare_available(projection):
            return None
        return MenuItem(
            "output_canvas.compare_outputs",
            app_text("Compare outputs"),
            checkable=True,
            checked=compare_enabled,
            checked_callback=self.set_compare_enabled,
            icon=(FIF.ACCEPT.icon() if compare_enabled else transparent_menu_icon()),
        )

    def _current_asset_has_path(self) -> bool:
        """Return whether the authorized current output has a local asset path."""

        image_id = self.current_image_id()
        if image_id is None or not self.image_is_authorized(image_id):
            return False
        metadata = self.image_metadata(image_id)
        return metadata is not None and bool(metadata.path.strip())

    def _projection_image_ids(self) -> tuple[UUID, ...]:
        """Return active-projection final outputs in their established order."""

        projection = self.projection()
        if projection is None:
            return ()
        return tuple(
            image.image_id
            for source in projection.sources
            for image in source.images_by_set.values()
        )


__all__ = ["OutputCanvasContextMenu"]
