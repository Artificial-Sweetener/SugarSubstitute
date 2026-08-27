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

"""Verify Output canvas picker presentation outside the widget host."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.output.output_canvas_picker_controller import (
    OutputCanvasPickerController,
    picker_row_width,
    picker_row_width_for_items,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem

_SetPickerCall = tuple[object, int, int, bool, Callable[[int], None]]
_NavPickerCall = tuple[
    object,
    tuple[CanvasNavPickerItem, ...],
    str,
    int | None,
    Callable[[str], None],
]


def test_picker_row_width_uses_widest_anchor_or_label() -> None:
    """Picker row width should preserve anchor width and fit measured labels."""

    assert picker_row_width(96, (72, 144, 88)) == 144
    assert picker_row_width(180, (72, 144, 88)) == 180


def test_picker_row_width_for_items_measures_item_labels() -> None:
    """Picker row width should be derived through an injected label measurer."""

    calls: list[str] = []
    items = (
        CanvasNavPickerItem("all", "All"),
        CanvasNavPickerItem("portrait", "Portrait"),
    )

    def _width_for_label(label: str) -> int:
        calls.append(label)
        return len(label) * 12

    assert picker_row_width_for_items(80, items, _width_for_label) == 96
    assert calls == ["All", "Portrait"]


def test_show_set_picker_uses_set_picker_when_available() -> None:
    """Set picker should include grid and active set data for normal mode."""

    calls: list[_SetPickerCall] = []
    controller = _controller(
        set_count=1,
        active_set_index=0,
        grid_available=True,
        set_picker_calls=calls,
    )

    controller.show_set_picker()

    assert calls == [("set-button", 1, 0, True, controller.on_set_selected)]


def test_show_set_picker_delegates_to_compare_picker_when_compare_enabled() -> None:
    """Compare mode should route set picker requests to compare-side picker."""

    calls: list[_SetPickerCall] = []
    selected: list[tuple[str, int]] = []
    controller = _controller(
        compare_state=OutputCompareState(enabled=True),
        compare_selection=OutputCompareSelection(None, 2, "txt"),
        compare_set_count=4,
        set_picker_calls=calls,
        selected_compare_sets=selected,
    )

    controller.show_set_picker()

    assert len(calls) == 1
    anchor, set_count, active_set_index, include_grid, callback = calls[0]
    assert anchor == "compare-set-base"
    assert set_count == 4
    assert active_set_index == 2
    assert include_grid is False

    callback(3)

    assert selected == [("base", 3)]


def test_scene_picker_items_sort_scenes_and_mark_unavailable_rows() -> None:
    """Scene picker items should include All, then scenes in display order."""

    preview_id = uuid4()
    controller = _controller(
        scene_groups={
            "later": OutputCanvasSceneGroup(
                scene_run_id="run-later",
                scene_key="later",
                title="Later",
                order=2,
                sources=(),
            ),
            "first": OutputCanvasSceneGroup(
                scene_run_id="run-first",
                scene_key="first",
                title="First",
                order=1,
                sources=(),
                preview_image_id=preview_id,
            ),
        }
    )

    items = controller.scene_picker_items()

    assert tuple(item.key for item in items) == ("all", "first", "later")
    assert tuple(item.label for item in items) == ("All", "First", "Later")
    assert tuple(item.enabled for item in items) == (True, True, False)


def test_show_scene_picker_uses_active_scene_key_and_width() -> None:
    """Scene picker should pass active key, row width, and callback."""

    calls: list[_NavPickerCall] = []
    controller = _controller(
        scene_count=2,
        active_scene_key="scene-a",
        scene_groups={
            "scene-a": OutputCanvasSceneGroup(
                scene_run_id="run-a",
                scene_key="scene-a",
                title="Scene A",
                order=1,
                sources=(),
                primary_image_id=uuid4(),
            )
        },
        scene_picker_calls=calls,
        scene_row_width=92,
    )

    controller.show_scene_picker()

    assert len(calls) == 1
    anchor, items, active_key, row_width, callback = calls[0]
    assert anchor == "scene-button"
    assert tuple(item.key for item in items) == ("all", "scene-a")
    assert active_key == "scene-a"
    assert row_width == 92
    assert callback is controller.on_scene_selected


def test_show_source_picker_uses_source_order_and_selected_callback() -> None:
    """Source picker should show visible sources in order with active source key."""

    calls: list[_NavPickerCall] = []
    controller = _controller(
        visible_sources={
            "txt": OutputCanvasSourceGroup("txt", "Text", {}),
            "up": OutputCanvasSourceGroup("up", "Upscale", {}),
        },
        active_source_key="up",
        source_picker_calls=calls,
        source_row_width=108,
    )

    controller.show_source_picker()

    assert len(calls) == 1
    anchor, items, active_key, row_width, callback = calls[0]
    assert anchor == "source-button"
    assert tuple(item.key for item in items) == ("txt", "up")
    assert tuple(item.label for item in items) == ("Text", "Upscale")
    assert active_key == "up"
    assert row_width == 108
    assert callback is controller.on_source_selected


def test_show_source_picker_delegates_to_compare_picker_when_compare_enabled() -> None:
    """Compare mode should route source picker requests to compare source picker."""

    calls: list[_NavPickerCall] = []
    selected: list[tuple[str, str]] = []
    controller = _controller(
        compare_state=OutputCompareState(enabled=True),
        compare_selection=OutputCompareSelection(None, 1, "txt"),
        compare_sources=(
            OutputCanvasSourceGroup("txt", "Text", {}),
            OutputCanvasSourceGroup("up", "Upscale", {}),
        ),
        source_picker_calls=calls,
        compare_source_row_width=144,
        selected_compare_sources=selected,
    )

    controller.show_source_picker()

    assert len(calls) == 1
    anchor, items, active_key, row_width, callback = calls[0]
    assert anchor == "compare-source-base"
    assert tuple(item.key for item in items) == ("txt", "up")
    assert active_key == "txt"
    assert row_width == 144

    callback("up")

    assert selected == [("base", "up")]


def test_show_compare_scene_picker_uses_scene_projection_and_selection() -> None:
    """Compare scene picker should use projection scene rows and compare callback."""

    calls: list[_NavPickerCall] = []
    selected: list[tuple[str, str]] = []
    source = OutputCanvasSourceGroup("txt", "Text", {})
    controller = _controller(
        projection=OutputCanvasProjection(
            sources=(source,),
            active_source_key="txt",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
            scene_count=2,
            scene_groups=(
                OutputCanvasSceneGroup(
                    scene_run_id="run-a",
                    scene_key="scene-a",
                    title="Scene A",
                    order=1,
                    sources=(source,),
                ),
                OutputCanvasSceneGroup(
                    scene_run_id="run-b",
                    scene_key="scene-b",
                    title="Scene B",
                    order=2,
                    sources=(),
                ),
            ),
        ),
        compare_selection=OutputCompareSelection("scene-a", 1, "txt"),
        scene_picker_calls=calls,
        scene_row_width=120,
        selected_compare_scenes=selected,
    )

    controller.show_compare_scene_picker("comparison")

    assert len(calls) == 1
    anchor, items, active_key, row_width, callback = calls[0]
    assert anchor == "compare-scene-comparison"
    assert tuple(item.key for item in items) == ("scene-a", "scene-b")
    assert tuple(item.enabled for item in items) == (True, False)
    assert active_key == "scene-a"
    assert row_width == 120

    callback("scene-b")

    assert selected == [("comparison", "scene-b")]


def _controller(
    *,
    compare_state: OutputCompareState | None = None,
    grid_available: bool = False,
    set_count: int = 2,
    active_set_index: int = 1,
    set_picker_calls: list[_SetPickerCall] | None = None,
    scene_count: int = 1,
    active_scene_overview: bool = False,
    active_scene_key: str | None = None,
    scene_groups: dict[str, OutputCanvasSceneGroup] | None = None,
    scene_picker_calls: list[_NavPickerCall] | None = None,
    scene_row_width: int = 80,
    active_source_key: str | None = None,
    visible_sources: dict[str, OutputCanvasSourceGroup] | None = None,
    source_picker_calls: list[_NavPickerCall] | None = None,
    source_row_width: int = 88,
    projection: OutputCanvasProjection | None = None,
    compare_selection: OutputCompareSelection | None = None,
    compare_sources: tuple[OutputCanvasSourceGroup, ...] = (),
    compare_set_count: int = 0,
    compare_source_row_width: int = 96,
    selected_compare_scenes: list[tuple[str, str]] | None = None,
    selected_compare_sets: list[tuple[str, int]] | None = None,
    selected_compare_sources: list[tuple[str, str]] | None = None,
) -> OutputCanvasPickerController:
    """Return a picker controller with deterministic collaborators."""

    active_set_calls = set_picker_calls if set_picker_calls is not None else []
    active_scene_calls = scene_picker_calls if scene_picker_calls is not None else []
    active_source_calls = source_picker_calls if source_picker_calls is not None else []
    active_selected_compare_scenes = (
        selected_compare_scenes if selected_compare_scenes is not None else []
    )
    active_selected_compare_sets = (
        selected_compare_sets if selected_compare_sets is not None else []
    )
    active_selected_compare_sources = (
        selected_compare_sources if selected_compare_sources is not None else []
    )
    controller = OutputCanvasPickerController(
        visible_compare_state=lambda: compare_state or OutputCompareState(),
        grid_available_for_visible_sources=lambda: grid_available,
        set_count=lambda: set_count,
        active_set_index=lambda: active_set_index,
        set_selector_button=lambda: "set-button",
        show_set_picker_for=lambda anchor, set_count_value, active_set_index_value, include_grid, selected_callback: (
            active_set_calls.append(
                (
                    anchor,
                    set_count_value,
                    active_set_index_value,
                    include_grid,
                    selected_callback,
                )
            )
        ),
        on_set_selected=_on_set_selected,
        scene_count=lambda: scene_count,
        active_scene_overview=lambda: active_scene_overview,
        active_scene_key=lambda: active_scene_key,
        scene_selector_button=lambda: "scene-button",
        scene_groups_by_key=lambda: scene_groups or {},
        scene_picker_row_width=lambda _items: scene_row_width,
        show_scene_picker_for=lambda anchor, items, active_key, row_width, selected_callback: (
            active_scene_calls.append(
                (anchor, items, active_key, row_width, selected_callback)
            )
        ),
        on_scene_selected=_on_scene_selected,
        active_source_key=lambda: active_source_key,
        source_selector_button=lambda: "source-button",
        visible_source_groups_by_key=lambda: visible_sources or {},
        source_picker_row_width=lambda _items: source_row_width,
        show_source_picker_for=lambda anchor, items, active_key, row_width, selected_callback: (
            active_source_calls.append(
                (anchor, items, active_key, row_width, selected_callback)
            )
        ),
        on_source_selected=_on_source_selected,
        output_projection=lambda: projection,
        compare_selection=lambda _side: compare_selection,
        compare_sources=lambda _side: compare_sources,
        compare_set_count=lambda _side: compare_set_count,
        compare_scene_button=lambda side: f"compare-scene-{side}",
        compare_set_button=lambda side: f"compare-set-{side}",
        compare_source_button=lambda side: f"compare-source-{side}",
        compare_source_picker_row_width=lambda _side, _items: compare_source_row_width,
        set_compare_scene=lambda side, scene_key: active_selected_compare_scenes.append(
            (side, scene_key)
        ),
        set_compare_set=lambda side, set_index: active_selected_compare_sets.append(
            (side, set_index)
        ),
        set_compare_source=lambda side, source_key: (
            active_selected_compare_sources.append((side, source_key))
        ),
    )
    return controller


def _on_set_selected(_set_index: int) -> None:
    """No-op set selection callback for tests."""


def _on_scene_selected(_scene_key: str) -> None:
    """No-op scene selection callback for tests."""


def _on_source_selected(_source_key: str) -> None:
    """No-op source selection callback for tests."""
