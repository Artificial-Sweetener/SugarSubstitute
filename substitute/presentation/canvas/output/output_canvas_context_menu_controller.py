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

"""Build and execute the Output canvas context menu outside the widget host."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_resolution import (
    output_compare_available,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.widgets.menu_model import (
    MenuEntry,
    MenuItem,
    MenuModel,
    MenuSeparator,
)


class OutputContextMenu(Protocol):
    """Support the menu operations needed by the Output canvas context menu."""

    def exec(self, pos: object, **kwargs: object) -> None:
        """Show the menu at ``pos`` with toolkit-specific keyword options."""


class OutputToggleSignal(Protocol):
    """Connect a checked-state callback to a toggle action."""

    def connect(self, callback: Callable[[bool], None]) -> None:
        """Connect ``callback`` to the toggle signal."""


class OutputToggleAction(Protocol):
    """Expose the QAction methods needed for the compare toggle."""

    toggled: OutputToggleSignal

    def setCheckable(self, checkable: bool) -> None:  # noqa: N802
        """Configure whether this action toggles checked state."""

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        """Set the current checked state."""

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        """Set whether the action can be triggered."""


class OutputCurrentImageProjector(Protocol):
    """Return the authorized current output image for a user event."""

    def current_image_id_for_event(self) -> UUID | None:
        """Return the current final-output image id when event access is allowed."""


@dataclass(frozen=True, slots=True)
class OutputCanvasContextMenuController:
    """Own Output canvas context-menu construction and action callbacks."""

    pane: Callable[[], object]
    action_parent: Callable[[], object]
    visible_compare_state: Callable[[], OutputCompareState]
    active_scene_overview: Callable[[], bool]
    active_set_index: Callable[[], int]
    output_projection: Callable[[], OutputCanvasProjection | None]
    set_compare_mode_enabled: Callable[[bool], None]
    menu_renderer: Callable[[object, MenuModel], OutputContextMenu]
    compare_enabled_icon: Callable[[], object]
    compare_disabled_icon: Callable[[], object]
    copy_icon: Callable[[], object]
    open_external_icon: Callable[[], object]
    open_all_external_icon: Callable[[], object]
    reveal_asset_icon: Callable[[], object]
    dock_action_icon: Callable[[], object]
    menu_animation_type: Callable[[], object]
    map_to_global: Callable[[object], object]
    current_image: Callable[[], object | None]
    clipboard_set_image: Callable[[object], None]
    output_route_projector: Callable[[], OutputCurrentImageProjector]
    final_output_payload: Callable[[UUID], object | None]
    final_output_metadata: Callable[[UUID], OutputImageMeta | None]
    open_single_external_editor: Callable[
        [], Callable[[object, OutputImageMeta], bool] | None
    ]
    open_all_external_editor: Callable[
        [],
        Callable[[list[tuple[object, OutputImageMeta]]], bool] | None,
    ]
    reveal_asset: Callable[[], Callable[[OutputImageMeta], bool] | None]
    allowed_image_ids: Callable[[], frozenset[UUID]]
    dock_action_text: Callable[[], str]
    request_dock_action: Callable[[], None]

    def show_context_menu(self, pos: object) -> None:
        """Show the output-canvas context menu for the current route state."""

        compare_enabled = self.visible_compare_state().enabled
        if not compare_enabled and (
            self.active_scene_overview() or self.active_set_index() == 0
        ):
            return

        menu = self.menu_renderer(
            self.pane(),
            MenuModel(entries=self._menu_entries(compare_enabled=compare_enabled)),
        )
        menu.exec(
            self.map_to_global(pos),
            aniType=self.menu_animation_type(),
        )

    def _menu_entries(self, *, compare_enabled: bool) -> tuple[MenuEntry, ...]:
        """Return output canvas context-menu entries for current state."""

        entries: list[MenuEntry] = []
        compare_entry = self._compare_entry(compare_enabled=compare_enabled)
        if compare_entry is not None:
            entries.extend((compare_entry, MenuSeparator()))
        entries.extend(
            (
                MenuItem(
                    "output_canvas.copy",
                    "Copy",
                    callback=self.copy_current_image,
                    icon=self.copy_icon(),
                ),
                MenuItem(
                    "output_canvas.open_current_external",
                    "Open in Photoshop",
                    callback=self.open_current_external,
                    icon=self.open_external_icon(),
                ),
                MenuItem(
                    "output_canvas.open_all_external",
                    "Open All in Photoshop",
                    callback=self.open_all_external,
                    icon=self.open_all_external_icon(),
                ),
                MenuItem(
                    "output_canvas.reveal_current_asset",
                    "Reveal in File Manager",
                    callback=self.reveal_current_asset,
                    enabled=self._current_asset_has_path(),
                    icon=self.reveal_asset_icon(),
                ),
                MenuSeparator(),
                MenuItem(
                    "output_canvas.dock_action",
                    self.dock_action_text(),
                    callback=self.request_dock_action,
                    icon=self.dock_action_icon(),
                ),
            )
        )
        return tuple(entries)

    def copy_current_image(self) -> None:
        """Copy the authorized current route image to the clipboard."""

        if self.output_route_projector().current_image_id_for_event() is None:
            return
        current_image = self.current_image()
        is_null = getattr(current_image, "isNull", None)
        if current_image is None or (callable(is_null) and bool(is_null())):
            return
        self.clipboard_set_image(current_image)

    def open_current_external(self) -> None:
        """Open the authorized current final output in the external editor."""

        open_external = self.open_single_external_editor()
        if open_external is None:
            return
        current_id = self.output_route_projector().current_image_id_for_event()
        if current_id is None:
            return
        image = self.final_output_payload(current_id)
        image_meta = self.final_output_metadata(current_id)
        if image is None or image_meta is None:
            return
        open_external(image, image_meta)

    def open_all_external(self) -> None:
        """Open every authorized final output in the active projection."""

        open_external = self.open_all_external_editor()
        if open_external is None:
            return
        prepared = [
            (image, image_meta)
            for image_id in self._projection_image_ids()
            if image_id in self.allowed_image_ids()
            for image in (self.final_output_payload(image_id),)
            for image_meta in (self.final_output_metadata(image_id),)
            if image is not None and image_meta is not None
        ]
        if prepared:
            open_external(prepared)

    def reveal_current_asset(self) -> None:
        """Reveal the authorized current final output in the native file manager."""

        reveal_asset = self.reveal_asset()
        if reveal_asset is None:
            return
        current_id = self.output_route_projector().current_image_id_for_event()
        if current_id is None:
            return
        image_meta = self.final_output_metadata(current_id)
        if image_meta is None or not image_meta.path.strip():
            return
        reveal_asset(image_meta)

    def _current_asset_has_path(self) -> bool:
        """Return whether the authorized current final output has a local path."""

        current_id = self.output_route_projector().current_image_id_for_event()
        if current_id is None:
            return False
        image_meta = self.final_output_metadata(current_id)
        return image_meta is not None and bool(image_meta.path.strip())

    def _compare_entry(
        self,
        *,
        compare_enabled: bool,
    ) -> MenuItem | None:
        """Return the compare toggle entry when a projection is active."""

        projection = self.output_projection()
        if projection is None:
            return None
        if not output_compare_available(projection):
            return None
        return MenuItem(
            "output_canvas.compare_outputs",
            "Compare outputs",
            enabled=True,
            checkable=True,
            checked=compare_enabled,
            checked_callback=self.set_compare_mode_enabled,
            icon=(
                self.compare_enabled_icon()
                if compare_enabled
                else self.compare_disabled_icon()
            ),
        )

    def _projection_image_ids(self) -> tuple[UUID, ...]:
        """Return final-output image ids in active projection order."""

        projection = self.output_projection()
        if projection is None:
            return ()
        return tuple(
            item.image_id
            for source in projection.sources
            for item in source.images_by_set.values()
        )


__all__ = [
    "OutputCanvasContextMenuController",
    "OutputContextMenu",
    "OutputCurrentImageProjector",
    "OutputToggleAction",
    "OutputToggleSignal",
]
