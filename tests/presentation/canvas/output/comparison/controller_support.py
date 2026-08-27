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

"""Provide typed Output comparison controller test doubles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
)


@dataclass(slots=True)
class PresenterSpy:
    """Record compare-state presenter calls and return configured states."""

    enabled_state: OutputCompareState = OutputCompareState(enabled=True)
    disabled_state: OutputCompareState = OutputCompareState(enabled=False)
    presentation_state: OutputCompareState = OutputCompareState(enabled=True)
    enabled_calls: tuple[
        tuple[OutputCanvasProjection, OutputCompareSelection | None],
        ...,
    ] = ()
    disabled_calls: tuple[OutputCompareState, ...] = ()
    presentation_calls: tuple[tuple[OutputCompareState, object], ...] = ()

    def state_for_enabled(
        self,
        projection: OutputCanvasProjection,
        *,
        current_selection: OutputCompareSelection | None,
    ) -> OutputCompareState:
        """Return configured enabled state and record the current selection."""

        self.enabled_calls = (*self.enabled_calls, (projection, current_selection))
        return self.enabled_state

    def state_for_disabled(self, state: OutputCompareState) -> OutputCompareState:
        """Return configured disabled state and record the source state."""

        self.disabled_calls = (*self.disabled_calls, state)
        return self.disabled_state

    def state_from_presentation_change(
        self,
        state: OutputCompareState,
        presentation: object,
    ) -> OutputCompareState:
        """Return configured workspace state and record the payload."""

        self.presentation_calls = (*self.presentation_calls, (state, presentation))
        return self.presentation_state


@dataclass(frozen=True, slots=True)
class ButtonGroup:
    """Hold opaque button objects for compare controller tests."""

    base_scene: object = object()
    comparison_scene: object = object()
    base_set: object = object()
    comparison_set: object = object()
    base_source: object = object()
    comparison_source: object = object()


@dataclass(frozen=True, slots=True)
class PickerItemStub:
    """Expose a picker label for row-width tests."""

    label: str


def build_controller(
    *,
    projection: OutputCanvasProjection | None = None,
    state: OutputCompareState | None = None,
    presenter: PresenterSpy | None = None,
    stored: list[OutputCompareState] | None = None,
    emitted: list[OutputCompareState] | None = None,
    compare_projection_syncs: (
        list[tuple[OutputCanvasProjection, OutputCompareState]] | None
    ) = None,
    sync_rendering_calls: list[None] | None = None,
    tabbar_updates: list[None] | None = None,
    active_source_keys: list[str] | None = None,
    active_set_indexes: list[int] | None = None,
    active_scene_keys: list[str | None] | None = None,
    sync_calls: list[str] | None = None,
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]] | None = None,
    set_count: int = 0,
    buttons: ButtonGroup | None = None,
    source_width_for_text: Callable[[str], int] | None = None,
    source_selector_min_width: int = 20,
    active_source_key: str | None = "source-a",
    active_set_index: int = 1,
    scene_count: int = 1,
    active_scene_key: str | None = None,
) -> OutputCompareController:
    """Return a compare controller with deterministic collaborators."""

    active_state = state or OutputCompareState()
    active_presenter = presenter or PresenterSpy()
    active_stored = stored if stored is not None else []
    active_emitted = emitted if emitted is not None else []
    active_projection_syncs = (
        compare_projection_syncs if compare_projection_syncs is not None else []
    )
    active_sync_rendering_calls = (
        sync_rendering_calls if sync_rendering_calls is not None else []
    )
    active_tabbar_updates = tabbar_updates if tabbar_updates is not None else []
    active_source_key_updates = (
        active_source_keys if active_source_keys is not None else []
    )
    active_set_index_updates = (
        active_set_indexes if active_set_indexes is not None else []
    )
    active_scene_key_updates = (
        active_scene_keys if active_scene_keys is not None else []
    )
    active_sync_calls = sync_calls if sync_calls is not None else []
    active_counted_sources = counted_sources if counted_sources is not None else []
    active_buttons = buttons or ButtonGroup()
    width_for_text = source_width_for_text or (lambda _text: 0)
    return OutputCompareController(
        output_projection=lambda: projection,
        visible_compare_state=lambda: active_state,
        output_compare_presenter=lambda: active_presenter,
        set_visible_compare_state=active_stored.append,
        emit_compare_changed=active_emitted.append,
        sync_compare_projection=lambda projection_value, state_value: (
            active_projection_syncs.append((projection_value, state_value))
        ),
        sync_compare_rendering=lambda: active_sync_rendering_calls.append(None),
        update_tabbar_container=lambda: active_tabbar_updates.append(None),
        active_source_key=lambda: active_source_key,
        active_set_index=lambda: active_set_index,
        scene_count=lambda: scene_count,
        active_scene_key=lambda: active_scene_key,
        set_active_source_key=active_source_key_updates.append,
        set_active_set_index=active_set_index_updates.append,
        set_active_scene_key=active_scene_key_updates.append,
        sync_scene_selector_button=lambda: active_sync_calls.append("scene"),
        sync_set_selector_button=lambda: active_sync_calls.append("set"),
        sync_source_selector_button=lambda: active_sync_calls.append("source"),
        sync_comparison_nav_buttons=lambda: active_sync_calls.append("comparison"),
        set_count_for_sources=lambda sources: record_sources(
            active_counted_sources,
            sources,
            set_count,
        ),
        base_scene_button=lambda: active_buttons.base_scene,
        comparison_scene_button=lambda: active_buttons.comparison_scene,
        base_set_button=lambda: active_buttons.base_set,
        comparison_set_button=lambda: active_buttons.comparison_set,
        base_source_button=lambda: active_buttons.base_source,
        comparison_source_button=lambda: active_buttons.comparison_source,
        source_selector_width_for_text=width_for_text,
        source_selector_min_width=source_selector_min_width,
    )


def build_projection() -> OutputCanvasProjection:
    """Return an empty projection sufficient for compare-state tests."""

    return OutputCanvasProjection(
        sources=(),
        active_source_key="source-a",
        active_set_index=2,
        active_uuid=None,
        set_count=2,
        scene_count=3,
        active_scene_key="scene-a",
    )


def build_source(
    source_key: str, *, label: str | None = None
) -> OutputCanvasSourceGroup:
    """Return a source group identified by key for controller tests."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=label or source_key,
        images_by_set={},
    )


def build_source_with_item(source_key: str, scene_key: str) -> OutputCanvasSourceGroup:
    """Return one source group with a concrete output item."""

    image_id = uuid4()
    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={
            1: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=ImageMeta(
                    workflow_name="Workflow",
                    cube_name="Output",
                    image_number=1,
                    suffix="",
                    path="E:/out.png",
                    source_key=source_key,
                    source_label=source_key,
                    scene_key=scene_key,
                ),
                set_index=1,
            )
        },
    )


def record_sources(
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]],
    sources: tuple[OutputCanvasSourceGroup, ...],
    count: int,
) -> int:
    """Record source-count input and return configured count."""

    counted_sources.append(sources)
    return count


def record_width(measured: list[str], text: str) -> int:
    """Record measured text and return deterministic label width."""

    measured.append(text)
    return 100 if text == "Long label" else 12
