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

"""Bind Output navigation chrome to the CuteCanvas document presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from PySide6.QtWidgets import QWidget
from cutecanvas import CanvasPresentation, CanvasPresentationKind
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    ensure_fluent_tooltip_filter,
)

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.application.workflows.output_preview_projection import (
    overlay_preview_scenes,
    overlay_preview_sources,
)
from substitute.application.workflows.output_preview_registry import OutputPreviewLane
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    selector_width_for_widget_text,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
    activate_output_item,
    select_output_scene,
    select_output_source,
    select_output_set,
    sync_output_scene_selector_button,
    sync_output_set_selector_button,
    sync_output_source_selector_button,
)
from substitute.presentation.canvas.output.output_canvas_picker_controller import (
    OutputCanvasPickerController,
    picker_row_width_for_items,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
    store_visible_output_compare_state,
    visible_output_compare_state,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresenter,
)
from substitute.presentation.canvas.output.output_compare_navigation_chrome import (
    sync_output_comparison_navigation_buttons,
)
from substitute.presentation.canvas.output.output_preview_navigation_presenter import (
    preview_source_grid_image_ids,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


@dataclass(slots=True, weakref_slot=True)
class OutputDocumentNavigation:
    """Own Output selector wiring independently of a legacy composition runtime."""

    host: OutputCanvas
    _source_tabs: OutputCanvasSourceTabsController = field(init=False)
    _compare: OutputCompareController = field(init=False)
    _picker: OutputCanvasPickerController = field(init=False)

    def __post_init__(self) -> None:
        """Build one source-tab, picker, and compare-control collaboration set."""

        self._source_tabs = OutputCanvasSourceTabsController(
            visible_sources=lambda: tuple(self._visible_sources().values()),
            cached_signature=lambda: getattr(
                self.host,
                "_source_tab_cache_signature",
                None,
            ),
            set_cached_signature=lambda signature: setattr(
                self.host,
                "_source_tab_cache_signature",
                signature,
            ),
            set_preferred_width=lambda width: setattr(
                self.host,
                "_source_tabbar_preferred_width",
                width,
            ),
            tabbar=lambda: self.host.tabbar,
            on_tab_changed=self._select_source,
            active_set_index=lambda: self.host.active_set_index,
            tooltip_filters=lambda: getattr(
                self.host,
                "_source_tab_tooltip_filters",
            ),
            measure_preferred_width=lambda: (
                OutputCanvasNavigationController.measure_tabbar_preferred_width(
                    self.host.tabbar
                )
            ),
            sync_source_selector=lambda: sync_output_source_selector_button(self.host),
            install_tooltip_filter=lambda tab_item, parent, delay: (
                ensure_fluent_tooltip_filter(
                    cast(QWidget, tab_item),
                    cast(QWidget, parent),
                    show_delay_ms=delay,
                    cursor_anchor=True,
                )
            ),
        )
        setattr(self.host, "_source_tabs_controller", self._source_tabs)
        self._compare = self._create_compare_controller()
        setattr(self.host, "_compare_controller", self._compare)
        self._picker = self._create_picker_controller()
        self._connect_controls()

    def synchronize_projection(self) -> None:
        """Refresh navigation chrome from the current document-backed projection."""

        projection = self.host._output_projection
        if projection is None:
            self._source_tabs.rebuild_source_tabs(active_source_key=None)
            update_output_tabbar_container(self.host)
            return
        if self.host.active_scene_overview:
            self.host.set_count = 0
            self._source_tabs.rebuild_source_tabs(active_source_key=None)
        else:
            sources = self._visible_sources()
            self.host.set_count = OutputCanvasRouteModel.set_count_for_sources(
                tuple(sources.values())
            )
            self._source_tabs.rebuild_source_tabs(
                active_source_key=self.host.active_source_key
            )
        sync_output_scene_selector_button(self.host)
        sync_output_set_selector_button(self.host)
        sync_output_source_selector_button(self.host)
        sync_output_comparison_navigation_buttons(self.host)
        update_output_tabbar_container(self.host)

    def visible_sources(self) -> dict[str, OutputCanvasSourceGroup]:
        """Return final sources overlaid with current transient placeholders."""

        return self._visible_sources()

    def scene_groups(self) -> dict[str, OutputCanvasSceneGroup]:
        """Return final scenes overlaid with current transient placeholders."""

        return self._scene_groups()

    def handle_workspace_presentation(self, presentation: CanvasPresentation) -> None:
        """Persist user divider movement forwarded by the public workspace state."""

        if presentation.kind is not CanvasPresentationKind.COMPARISON:
            return
        comparison = presentation.comparison
        if comparison is None:
            return
        current = visible_output_compare_state(self.host)
        orientation = comparison.orientation.value
        updated = OutputCompareState(
            enabled=True,
            base=current.base,
            comparison=current.comparison,
            split_position=comparison.split_position,
            orientation=orientation,
        )
        if updated == current:
            return
        store_visible_output_compare_state(self.host, updated)
        self._emit_compare_changed(updated)

    def activate_grid_target(self, image_id: object) -> bool:
        """Translate a workspace composition target to one product navigation intent."""

        projection = self.host._output_projection
        if projection is None:
            return False
        if self.host.active_scene_overview:
            for scene in self._scene_groups().values():
                if image_id in {scene.preview_image_id, scene.primary_image_id}:
                    self.host.release_preview_navigation()
                    select_output_scene(
                        self.host,
                        scene.scene_key,
                        scene_groups_by_key=self._scene_groups(),
                        update_tabbar_container=lambda: update_output_tabbar_container(
                            self.host
                        ),
                    )
                    return True
            return False
        for source in self._visible_sources().values():
            for item in source.images_by_set.values():
                if item.image_id == image_id:
                    if self._activate_preview_item(source.source_key, item):
                        return True
                    self.host.release_preview_navigation()
                    activate_output_item(
                        self.host,
                        source.source_key,
                        item,
                        update_tabbar_container=lambda: update_output_tabbar_container(
                            self.host
                        ),
                    )
                    return True
        return False

    def set_compare_mode_enabled(self, enabled: bool) -> None:
        """Apply the existing compare-mode action from the Output context menu."""

        self._compare.set_compare_mode_enabled(enabled)

    def _connect_controls(self) -> None:
        """Attach selector callbacks to their document-navigation owners."""

        self.host.tabbar.currentItemChanged.connect(self._select_source)
        self.host.scene_selector_button.clicked.connect(
            lambda: self._picker.show_scene_picker()
        )
        self.host.set_selector_button.clicked.connect(
            lambda: self._picker.show_set_picker()
        )
        self.host.source_selector_button.clicked.connect(
            lambda: self._picker.show_source_picker()
        )
        self.host.comparison_scene_selector_button.clicked.connect(
            lambda: self._picker.show_compare_scene_picker("comparison")
        )
        self.host.comparison_set_selector_button.clicked.connect(
            lambda: self._picker.show_compare_set_picker("comparison")
        )
        self.host.comparison_source_selector_button.clicked.connect(
            lambda: self._picker.show_compare_source_picker("comparison")
        )

    def _create_compare_controller(self) -> OutputCompareController:
        """Build compare selector state without legacy rendering adapters."""

        presenter = OutputComparePresenter(self.host.route_projector)
        return OutputCompareController(
            output_projection=lambda: self.host._output_projection,
            visible_compare_state=lambda: visible_output_compare_state(self.host),
            output_compare_presenter=lambda: presenter,
            set_visible_compare_state=lambda state: store_visible_output_compare_state(
                self.host,
                state,
            ),
            emit_compare_changed=self._emit_compare_changed,
            sync_compare_projection=lambda _projection, _state: (
                self.synchronize_projection()
            ),
            sync_compare_rendering=self.synchronize_projection,
            update_tabbar_container=lambda: update_output_tabbar_container(self.host),
            active_source_key=lambda: self.host.active_source_key,
            active_set_index=lambda: self.host.active_set_index,
            scene_count=lambda: self.host.scene_count,
            active_scene_key=lambda: self.host.active_scene_key,
            set_active_source_key=lambda source_key: setattr(
                self.host,
                "active_source_key",
                source_key,
            ),
            set_active_set_index=lambda set_index: setattr(
                self.host,
                "active_set_index",
                set_index,
            ),
            set_active_scene_key=lambda scene_key: setattr(
                self.host,
                "active_scene_key",
                scene_key,
            ),
            sync_scene_selector_button=lambda: sync_output_scene_selector_button(
                self.host
            ),
            sync_set_selector_button=lambda: sync_output_set_selector_button(self.host),
            sync_source_selector_button=lambda: sync_output_source_selector_button(
                self.host
            ),
            sync_comparison_nav_buttons=lambda: (
                sync_output_comparison_navigation_buttons(self.host)
            ),
            set_count_for_sources=OutputCanvasRouteModel.set_count_for_sources,
            base_scene_button=lambda: self.host.scene_selector_button,
            comparison_scene_button=lambda: self.host.comparison_scene_selector_button,
            base_set_button=lambda: self.host.set_selector_button,
            comparison_set_button=lambda: self.host.comparison_set_selector_button,
            base_source_button=lambda: self.host.source_selector_button,
            comparison_source_button=lambda: (
                self.host.comparison_source_selector_button
            ),
            source_selector_width_for_text=self._source_width_for_text,
            source_selector_min_width=_SOURCE_SELECTOR_MIN_WIDTH,
        )

    def _create_picker_controller(self) -> OutputCanvasPickerController:
        """Build selector menus using the current document-backed projection."""

        return OutputCanvasPickerController(
            visible_compare_state=lambda: visible_output_compare_state(self.host),
            grid_available_for_visible_sources=lambda: (
                self.host.active_set_index == 0
                or OutputCanvasRouteModel.first_batch_overview_source_key(
                    self._visible_sources()
                )
                is not None
            ),
            set_count=lambda: self.host.set_count,
            active_set_index=lambda: self.host.active_set_index,
            set_selector_button=lambda: self.host.set_selector_button,
            show_set_picker_for=lambda anchor, count, active, include_grid, callback: (
                self.host._set_picker.show_for(
                    cast(QWidget, anchor),
                    set_count=count,
                    active_set_index=active,
                    include_grid=include_grid,
                    selected_callback=callback,
                )
            ),
            on_set_selected=self._select_set,
            scene_count=lambda: self.host.scene_count,
            active_scene_overview=lambda: self.host.active_scene_overview,
            active_scene_key=lambda: self.host.active_scene_key,
            scene_selector_button=lambda: self.host.scene_selector_button,
            scene_groups_by_key=self._scene_groups,
            scene_picker_row_width=self._scene_picker_width,
            show_scene_picker_for=lambda anchor, items, active, width, callback: (
                self.host._scene_picker.show_for(
                    cast(QWidget, anchor),
                    items=items,
                    active_key=active,
                    row_width=width,
                    selected_callback=callback,
                )
            ),
            on_scene_selected=self._select_scene,
            active_source_key=lambda: self.host.active_source_key,
            source_selector_button=lambda: self.host.source_selector_button,
            visible_source_groups_by_key=self._visible_sources,
            source_picker_row_width=self._source_picker_width,
            show_source_picker_for=lambda anchor, items, active, width, callback: (
                self.host._source_picker.show_for(
                    cast(QWidget, anchor),
                    items=items,
                    active_key=active,
                    row_width=width,
                    selected_callback=callback,
                )
            ),
            on_source_selected=self._select_source,
            output_projection=lambda: self.host._output_projection,
            compare_selection=self._compare.compare_selection,
            compare_sources=self._compare.compare_sources,
            compare_set_count=self._compare.compare_set_count,
            compare_scene_button=self._compare.compare_scene_button,
            compare_set_button=self._compare.compare_set_button,
            compare_source_button=self._compare.compare_source_button,
            compare_source_picker_row_width=lambda _side, items: (
                self._source_picker_width(items)
            ),
            set_compare_scene=self._compare.set_compare_scene,
            set_compare_set=self._compare.set_compare_set,
            set_compare_source=self._compare.set_compare_source,
        )

    def _select_set(self, set_index: int) -> None:
        """Apply one set picker choice through existing product navigation policy."""

        source_key = self.host.active_source_key
        source = self._visible_sources().get(source_key or "")
        if source is not None:
            item = source.images_by_set.get(set_index)
            if item is not None and self._activate_preview_item(
                source.source_key,
                item,
            ):
                return
        self.host.release_preview_navigation()
        select_output_set(
            self.host,
            set_index,
            source_groups_by_key=self._visible_sources(),
            update_tabbar_container=lambda: update_output_tabbar_container(self.host),
        )

    def _select_source(self, source_key: str) -> None:
        """Apply one source tab or picker choice through product navigation policy."""

        source = self._visible_sources().get(source_key)
        preview_grid_ids = (
            ()
            if source is None or self.host.active_set_index != 0
            else preview_source_grid_image_ids(source, self.host._preview_registry)
        )
        if preview_grid_ids:
            self.host.release_preview_navigation()
            select_output_source(
                self.host,
                source_key,
                source_groups_by_key=self._visible_sources(),
                update_tabbar_container=lambda: update_output_tabbar_container(
                    self.host
                ),
            )
            self.host.present_preview_grid(preview_grid_ids)
            return
        item = (
            None
            if source is None
            else source.images_by_set.get(self.host.active_set_index)
        )
        if item is not None and self._activate_preview_item(source_key, item):
            return
        self.host.release_preview_navigation()
        select_output_source(
            self.host,
            source_key,
            source_groups_by_key=self._visible_sources(),
            update_tabbar_container=lambda: update_output_tabbar_container(self.host),
        )

    def _activate_preview_item(
        self,
        source_key: str,
        item: OutputCanvasImageItem,
    ) -> bool:
        """Activate one preview placeholder without persisting a nonexistent final UUID."""

        lane = self.host._preview_registry.lane_for_id(item.image_id)
        if lane is None:
            return False
        activate_output_item(
            self.host,
            source_key,
            item,
            emit_selection=False,
            update_tabbar_container=lambda: update_output_tabbar_container(self.host),
        )
        self.host.present_preview_selection(lane.preview_id)
        return True

    def _select_scene(self, scene_key: str) -> None:
        """Apply one scene picker choice through product navigation policy."""

        self.host._preview_navigation.select_scene(scene_key, self._scene_groups())

    def _visible_sources(self) -> dict[str, OutputCanvasSourceGroup]:
        """Return sources valid for the current scene-level navigation scope."""

        projection = self.host._output_projection
        if projection is None or self.host.active_scene_overview:
            return {}
        scene_groups = self._scene_groups()
        active_scene = (
            scene_groups.get(self.host.active_scene_key)
            if self.host.active_scene_key
            else None
        )
        if active_scene is not None:
            return {source.source_key: source for source in active_scene.sources}
        if self.host.scene_count <= 1:
            sources = overlay_preview_sources(
                projection.sources,
                self._preview_lanes(),
                scene_key=None,
            )
            return {source.source_key: source for source in sources}
        return {}

    def _scene_groups(self) -> dict[str, OutputCanvasSceneGroup]:
        """Return current final scene groups keyed by their stable workflow identity."""

        projection = self.host._output_projection
        scenes = overlay_preview_scenes(
            () if projection is None else projection.scene_groups,
            self._preview_lanes(),
        )
        return {scene.scene_key: scene for scene in scenes}

    def _preview_lanes(self) -> tuple[OutputPreviewLane, ...]:
        """Return preview lanes belonging to the bound Output session."""

        session = self.host._output_session
        registry = self.host._preview_registry
        if session is None or registry is None:
            return ()
        return registry.lanes_for_session(session)

    def _scene_picker_width(self, items: tuple[CanvasNavPickerItem, ...]) -> int:
        """Return a scene menu width that fits its anchor and localized labels."""

        return picker_row_width_for_items(
            self.host.scene_selector_button.width(),
            items,
            lambda label: selector_width_for_widget_text(
                label,
                widget=self.host.scene_selector_button,
                minimum_width=_SCENE_SELECTOR_MIN_WIDTH,
                maximum_width=_SCENE_SELECTOR_MAX_WIDTH,
                horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
            ),
        )

    def _source_picker_width(self, items: tuple[CanvasNavPickerItem, ...]) -> int:
        """Return a source menu width that fits its anchor and localized labels."""

        return picker_row_width_for_items(
            self.host.source_selector_button.width(),
            items,
            self._source_width_for_text,
        )

    def _source_width_for_text(self, text: str) -> int:
        """Measure one source label through the production selector widget."""

        return selector_width_for_widget_text(
            text,
            widget=self.host.source_selector_button,
            minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
            maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
        )

    def _emit_compare_changed(self, state: OutputCompareState) -> None:
        """Publish one user-visible compare state mutation to application ownership."""

        self.host.activeOutputCompareChanged.emit(state)


__all__ = ["OutputDocumentNavigation"]
