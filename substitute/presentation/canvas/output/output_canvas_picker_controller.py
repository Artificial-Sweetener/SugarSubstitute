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

"""Coordinate Output canvas set, scene, and source picker presentation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
    output_scene_title_text,
    output_source_label_text,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem


def picker_row_width(
    current_width: int,
    label_widths: tuple[int, ...],
) -> int:
    """Return a picker row width that fits the anchor and every label."""

    return max(current_width, *label_widths)


def picker_row_width_for_items(
    current_width: int,
    items: tuple[CanvasNavPickerItem, ...],
    width_for_label: Callable[[str], int],
) -> int:
    """Return picker row width from anchor width and measured item labels."""

    return picker_row_width(
        current_width,
        tuple(width_for_label(item.label) for item in items),
    )


@dataclass(frozen=True, slots=True)
class OutputCanvasPickerController:
    """Own non-compare Output canvas picker presentation decisions."""

    visible_compare_state: Callable[[], OutputCompareState]
    grid_available_for_visible_sources: Callable[[], bool]
    set_count: Callable[[], int]
    active_set_index: Callable[[], int]
    set_selector_button: Callable[[], object]
    show_set_picker_for: Callable[
        [object, int, int, bool, Callable[[int], None]],
        None,
    ]
    on_set_selected: Callable[[int], None]
    scene_count: Callable[[], int]
    active_scene_overview: Callable[[], bool]
    active_scene_key: Callable[[], str | None]
    scene_selector_button: Callable[[], object]
    scene_groups_by_key: Callable[[], Mapping[str, OutputCanvasSceneGroup]]
    scene_picker_row_width: Callable[[tuple[CanvasNavPickerItem, ...]], int]
    show_scene_picker_for: Callable[
        [
            object,
            tuple[CanvasNavPickerItem, ...],
            str,
            int | None,
            Callable[[str], None],
        ],
        None,
    ]
    on_scene_selected: Callable[[str], None]
    active_source_key: Callable[[], str | None]
    source_selector_button: Callable[[], object]
    visible_source_groups_by_key: Callable[[], Mapping[str, OutputCanvasSourceGroup]]
    source_picker_row_width: Callable[[tuple[CanvasNavPickerItem, ...]], int]
    show_source_picker_for: Callable[
        [
            object,
            tuple[CanvasNavPickerItem, ...],
            str,
            int | None,
            Callable[[str], None],
        ],
        None,
    ]
    on_source_selected: Callable[[str], None]
    output_projection: Callable[[], OutputCanvasProjection | None]
    compare_selection: Callable[[str], OutputCompareSelection | None]
    compare_sources: Callable[[str], tuple[OutputCanvasSourceGroup, ...]]
    compare_set_count: Callable[[str], int]
    compare_scene_button: Callable[[str], object]
    compare_set_button: Callable[[str], object]
    compare_source_button: Callable[[str], object]
    compare_source_picker_row_width: Callable[
        [str, tuple[CanvasNavPickerItem, ...]],
        int,
    ]
    set_compare_scene: Callable[[str, str], None]
    set_compare_set: Callable[[str, int], None]
    set_compare_source: Callable[[str, str], None]

    def show_set_picker(self) -> None:
        """Show the batch set picker for the active Output selection."""

        if self.visible_compare_state().enabled:
            self.show_compare_set_picker("base")
            return
        include_grid = self.grid_available_for_visible_sources()
        set_count = self.set_count()
        if set_count <= 1 and not include_grid:
            return
        self.show_set_picker_for(
            self.set_selector_button(),
            set_count,
            self.active_set_index(),
            include_grid,
            self.on_set_selected,
        )

    def show_scene_picker(self) -> None:
        """Show the scene picker for multi-scene output projections."""

        if self.visible_compare_state().enabled:
            self.show_compare_scene_picker("base")
            return
        if self.scene_count() <= 1:
            return
        items = self.scene_picker_items()
        self.show_scene_picker_for(
            self.scene_selector_button(),
            items,
            self._active_scene_picker_key(),
            self.scene_picker_row_width(items),
            self.on_scene_selected,
        )

    def show_source_picker(self) -> None:
        """Show the source picker when source tabs are collapsed."""

        if self.visible_compare_state().enabled:
            self.show_compare_source_picker("base")
            return
        if (
            len(self.visible_source_groups_by_key()) <= 1
            or self.active_scene_overview()
        ):
            return
        items = self.source_picker_items()
        if not items:
            return
        self.show_source_picker_for(
            self.source_selector_button(),
            items,
            self.active_source_key() or items[0].key,
            self.source_picker_row_width(items),
            self.on_source_selected,
        )

    def show_compare_scene_picker(self, side: str) -> None:
        """Show the scene picker for one compare side."""

        projection = self.output_projection()
        if projection is None or projection.scene_count <= 1:
            return
        selection = self.compare_selection(side)
        items = tuple(
            CanvasNavPickerItem(
                scene.scene_key,
                render_application_text(output_scene_title_text(scene)),
                enabled=bool(scene.sources),
            )
            for scene in projection.scene_groups
        )
        if not items:
            return
        self.show_scene_picker_for(
            self.compare_scene_button(side),
            items,
            (selection.scene_key if selection else items[0].key) or "",
            self.scene_picker_row_width(items),
            lambda scene_key: self.set_compare_scene(side, scene_key),
        )

    def show_compare_set_picker(self, side: str) -> None:
        """Show the set picker for one compare side."""

        selection = self.compare_selection(side)
        if selection is None:
            return
        set_count = self.compare_set_count(side)
        if set_count <= 1:
            return
        self.show_set_picker_for(
            self.compare_set_button(side),
            set_count,
            selection.set_index,
            False,
            lambda set_index: self.set_compare_set(side, set_index),
        )

    def show_compare_source_picker(self, side: str) -> None:
        """Show the source picker for one compare side."""

        selection = self.compare_selection(side)
        sources = self.compare_sources(side)
        if selection is None or len(sources) <= 1:
            return
        items = tuple(
            CanvasNavPickerItem(
                source.source_key,
                render_application_text(output_source_label_text(source)),
            )
            for source in sources
        )
        self.show_source_picker_for(
            self.compare_source_button(side),
            items,
            selection.source_key,
            self.compare_source_picker_row_width(side, items),
            lambda source_key: self.set_compare_source(side, source_key),
        )

    def scene_picker_items(self) -> tuple[CanvasNavPickerItem, ...]:
        """Return scene selector rows with All first and scene titles after it."""

        items = [CanvasNavPickerItem("all", render_application_text(app_text("All")))]
        for scene in sorted(
            self.scene_groups_by_key().values(),
            key=lambda group: group.order,
        ):
            items.append(
                CanvasNavPickerItem(
                    scene.scene_key,
                    render_application_text(output_scene_title_text(scene)),
                    enabled=scene.primary_image_id is not None
                    or scene.preview_image_id is not None,
                )
            )
        return tuple(items)

    def source_picker_items(self) -> tuple[CanvasNavPickerItem, ...]:
        """Return source selector rows in source-tab order."""

        return tuple(
            CanvasNavPickerItem(
                source.source_key,
                render_application_text(output_source_label_text(source)),
            )
            for source in self.visible_source_groups_by_key().values()
        )

    def _active_scene_picker_key(self) -> str:
        """Return the currently active scene picker key."""

        if self.active_scene_overview():
            return "all"
        return self.active_scene_key() or "all"


__all__ = [
    "OutputCanvasPickerController",
    "picker_row_width",
    "picker_row_width_for_items",
]
