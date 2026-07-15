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

"""Coordinate Output compare-mode state outside the canvas widget."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_resolution import (
    default_output_compare_state,
    reconcile_output_compare_state,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)


class OutputCompareStatePresenter(Protocol):
    """Build compare states from UI intent and QPane divider payloads."""

    def state_for_enabled(
        self,
        projection: OutputCanvasProjection,
        *,
        current_selection: OutputCompareSelection | None,
    ) -> OutputCompareState:
        """Return the compare state for enabling compare mode."""

    def state_for_disabled(self, state: OutputCompareState) -> OutputCompareState:
        """Return the compare state for disabling compare mode."""

    def state_from_qpane_change(
        self,
        state: OutputCompareState,
        qpane_state: object,
    ) -> OutputCompareState:
        """Return compare state updated from a QPane comparison payload."""


class OutputComparePickerItem(Protocol):
    """Expose the picker label needed for compare source row sizing."""

    @property
    def label(self) -> str:
        """Return the display label measured for picker row width."""
        ...


def visible_output_compare_state(host: object) -> OutputCompareState:
    """Return compare state used for current Output compare-control rendering."""

    state = getattr(host, "_visible_compare_state", None)
    if isinstance(state, OutputCompareState):
        return state
    return getattr(host, "output_compare_state", OutputCompareState())


def store_visible_output_compare_state(
    host: object,
    state: OutputCompareState,
) -> None:
    """Store current compare control state without changing workflow authority."""

    setattr(host, "_visible_compare_state", state)
    if hasattr(host, "output_compare_state"):
        setattr(host, "output_compare_state", state)


@dataclass(frozen=True, slots=True)
class OutputCompareProjectionPlan:
    """Describe widget state required to project active compare selections."""

    state: OutputCompareState
    base: OutputCompareSelection | None
    sources: tuple[OutputCanvasSourceGroup, ...]
    set_count: int


@dataclass(frozen=True, slots=True)
class OutputCompareController:
    """Own compare-mode UI state orchestration for the Output canvas."""

    output_projection: Callable[[], OutputCanvasProjection | None]
    visible_compare_state: Callable[[], OutputCompareState]
    output_compare_presenter: Callable[[], OutputCompareStatePresenter]
    set_visible_compare_state: Callable[[OutputCompareState], None]
    emit_compare_changed: Callable[[OutputCompareState], None]
    sync_compare_projection: Callable[
        [OutputCanvasProjection, OutputCompareState],
        None,
    ]
    sync_compare_rendering: Callable[[], None]
    update_tabbar_container: Callable[[], None]
    active_source_key: Callable[[], str | None]
    active_set_index: Callable[[], int]
    scene_count: Callable[[], int]
    active_scene_key: Callable[[], str | None]
    set_active_source_key: Callable[[str], None]
    set_active_set_index: Callable[[int], None]
    set_active_scene_key: Callable[[str | None], None]
    sync_scene_selector_button: Callable[[], None]
    sync_set_selector_button: Callable[[], None]
    sync_source_selector_button: Callable[[], None]
    sync_comparison_nav_buttons: Callable[[], None]
    set_count_for_sources: Callable[[tuple[OutputCanvasSourceGroup, ...]], int]
    base_scene_button: Callable[[], object]
    comparison_scene_button: Callable[[], object]
    base_set_button: Callable[[], object]
    comparison_set_button: Callable[[], object]
    base_source_button: Callable[[], object]
    comparison_source_button: Callable[[], object]
    source_selector_width_for_text: Callable[[str], int]
    source_selector_min_width: int

    def set_compare_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable compare mode from local Output canvas actions."""

        projection = self.output_projection()
        if enabled:
            if projection is None:
                return
            next_state = self.output_compare_presenter().state_for_enabled(
                projection,
                current_selection=self.current_output_compare_selection(),
            )
        else:
            next_state = self.output_compare_presenter().state_for_disabled(
                self.visible_compare_state(),
            )
        self.set_visible_compare_state(next_state)
        self.emit_compare_changed(next_state)
        if enabled and projection is not None:
            self.sync_compare_projection(projection, next_state)
        else:
            self.sync_compare_rendering()
            self.update_tabbar_container()

    def current_output_compare_selection(self) -> OutputCompareSelection | None:
        """Return the current concrete Output selection, if one is active."""

        return OutputCanvasRouteModel.current_output_compare_selection(
            active_source_key=self.active_source_key(),
            active_set_index=self.active_set_index(),
            scene_count=self.scene_count(),
            active_scene_key=self.active_scene_key(),
        )

    def on_pane_comparison_changed(self, qpane_state: object) -> None:
        """Store QPane divider changes in visible compare state."""

        state = self.visible_compare_state()
        next_state = self.output_compare_presenter().state_from_qpane_change(
            state,
            qpane_state,
        )
        if next_state == state:
            return
        self.set_visible_compare_state(next_state)
        self.emit_compare_changed(next_state)

    def compare_sources_for_selection(
        self,
        projection: OutputCanvasProjection,
        selection: OutputCompareSelection,
    ) -> tuple[OutputCanvasSourceGroup, ...]:
        """Return sources available to one compare selection."""

        if projection.scene_count <= 1:
            return projection.sources
        for scene in projection.scene_groups:
            if scene.scene_key == selection.scene_key:
                return scene.sources
        return ()

    def compare_projection_plan(
        self,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
    ) -> OutputCompareProjectionPlan:
        """Return active widget state for synchronizing compare projection."""

        next_state = state
        base = next_state.base
        if base is None:
            next_state = default_output_compare_state(projection)
            base = next_state.base
        sources = (
            self.compare_sources_for_selection(projection, base)
            if base is not None
            else ()
        )
        return OutputCompareProjectionPlan(
            state=next_state,
            base=base,
            sources=sources,
            set_count=self.set_count_for_sources(sources),
        )

    def compare_selection(self, side: str) -> OutputCompareSelection | None:
        """Return the selection for one compare side."""

        state = self.visible_compare_state()
        return state.base if side == "base" else state.comparison

    def set_compare_selection(
        self,
        side: str,
        selection: OutputCompareSelection,
    ) -> None:
        """Replace one compare-side selection and resynchronize the canvas."""

        state = self.visible_compare_state()
        next_state = OutputCompareState(
            enabled=state.enabled,
            base=selection if side == "base" else state.base,
            comparison=selection if side == "comparison" else state.comparison,
            split_position=state.split_position,
            orientation=state.orientation,
        )
        projection = self.output_projection()
        next_visible_state = (
            reconcile_output_compare_state(projection, next_state)
            if projection is not None
            else next_state
        )
        self.set_visible_compare_state(next_visible_state)
        self.emit_compare_changed(next_visible_state)
        if side == "base" and next_visible_state.base is not None:
            base = next_visible_state.base
            self.set_active_scene_key(
                base.scene_key if self.scene_count() > 1 else None
            )
            self.set_active_source_key(base.source_key)
            self.set_active_set_index(base.set_index)
        self.sync_scene_selector_button()
        self.sync_set_selector_button()
        self.sync_source_selector_button()
        self.sync_comparison_nav_buttons()
        self.sync_compare_rendering()
        self.update_tabbar_container()

    def set_compare_scene(self, side: str, scene_key: str) -> None:
        """Set one compare side's scene and preserve nearest set/source."""

        if self.output_projection() is None:
            return
        selection = self.compare_selection(side)
        if selection is None:
            return
        candidate = OutputCompareSelection(
            scene_key=scene_key,
            set_index=selection.set_index,
            source_key=selection.source_key,
        )
        self.set_compare_selection(side, self.nearest_compare_selection(candidate))

    def set_compare_set(self, side: str, set_index: int) -> None:
        """Set one compare side's batch index."""

        selection = self.compare_selection(side)
        if selection is None:
            return
        self.set_compare_selection(
            side,
            self.nearest_compare_selection(
                OutputCompareSelection(
                    scene_key=selection.scene_key,
                    set_index=max(1, set_index),
                    source_key=selection.source_key,
                )
            ),
        )

    def set_compare_source(self, side: str, source_key: str) -> None:
        """Set one compare side's source output."""

        selection = self.compare_selection(side)
        if selection is None:
            return
        self.set_compare_selection(
            side,
            self.nearest_compare_selection(
                OutputCompareSelection(
                    scene_key=selection.scene_key,
                    set_index=selection.set_index,
                    source_key=source_key,
                )
            ),
        )

    def nearest_compare_selection(
        self,
        selection: OutputCompareSelection,
    ) -> OutputCompareSelection:
        """Return a valid compare selection nearest to a requested value."""

        projection = self.output_projection()
        if projection is None:
            return selection
        reconciled = reconcile_output_compare_state(
            projection,
            OutputCompareState(
                enabled=True,
                base=selection,
                comparison=selection,
            ),
        )
        return reconciled.base or selection

    def compare_sources(self, side: str) -> tuple[OutputCanvasSourceGroup, ...]:
        """Return sources available to one compare side."""

        projection = self.output_projection()
        selection = self.compare_selection(side)
        if projection is None or selection is None:
            return ()
        return self.compare_sources_for_selection(projection, selection)

    def compare_source_label(self, selection: OutputCompareSelection) -> str:
        """Return display label for one compare source selection."""

        projection = self.output_projection()
        if projection is None:
            return "Output"
        for source in self.compare_sources_for_selection(projection, selection):
            if source.source_key == selection.source_key:
                return source.label
        return "Output"

    def compare_set_count(self, side: str) -> int:
        """Return set count available to one compare side."""

        return self.set_count_for_sources(self.compare_sources(side))

    def compare_scene_button(self, side: str) -> object:
        """Return the scene selector button for one compare side."""

        return (
            self.base_scene_button()
            if side == "base"
            else self.comparison_scene_button()
        )

    def compare_set_button(self, side: str) -> object:
        """Return the set selector button for one compare side."""

        return (
            self.base_set_button() if side == "base" else self.comparison_set_button()
        )

    def compare_source_button(self, side: str) -> object:
        """Return the source selector button for one compare side."""

        return (
            self.base_source_button()
            if side == "base"
            else self.comparison_source_button()
        )

    def compare_source_picker_row_width(
        self,
        items: tuple[OutputComparePickerItem, ...],
    ) -> int:
        """Return source picker row width for one compare side."""

        label_widths = (
            self.source_selector_width_for_text(item.label) for item in items
        )
        return max(self.source_selector_min_width, *label_widths)


__all__ = [
    "OutputCompareController",
    "OutputComparePickerItem",
    "OutputCompareProjectionPlan",
    "OutputCompareStatePresenter",
    "store_visible_output_compare_state",
    "visible_output_compare_state",
]
