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

"""Verify Output compare-mode state orchestration outside the widget."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
    store_visible_output_compare_state,
    visible_output_compare_state,
)


def test_visible_output_compare_state_reads_installed_visible_state() -> None:
    """Visible compare state should prefer the host's rendered-state slot."""

    state = OutputCompareState(enabled=True)
    host = SimpleNamespace(
        _visible_compare_state=state,
        output_compare_state=OutputCompareState(enabled=False),
    )

    assert visible_output_compare_state(host) is state


def test_store_visible_output_compare_state_updates_fake_host_mirror() -> None:
    """Lightweight hosts should mirror visible compare state for old fakes."""

    state = OutputCompareState(enabled=True)
    host = SimpleNamespace(output_compare_state=OutputCompareState())

    store_visible_output_compare_state(host, state)

    assert host._visible_compare_state is state
    assert host.output_compare_state is state


def test_set_compare_mode_enabled_uses_current_selection_context() -> None:
    """Enabling compare mode should seed presenter state from active Output focus."""

    projection = _projection()
    next_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 2, "source-a"),
        comparison=OutputCompareSelection("scene-a", 2, "source-b"),
    )
    presenter = _Presenter(enabled_state=next_state)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    synced: list[tuple[OutputCanvasProjection, OutputCompareState]] = []
    controller = _controller(
        projection=projection,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
        compare_projection_syncs=synced,
        active_source_key="source-a",
        active_set_index=2,
        scene_count=3,
        active_scene_key="scene-a",
    )

    controller.set_compare_mode_enabled(True)

    assert presenter.enabled_calls == (
        (projection, OutputCompareSelection("scene-a", 2, "source-a")),
    )
    assert stored == [next_state]
    assert emitted == [next_state]
    assert synced == [(projection, next_state)]


def test_set_compare_mode_disabled_preserves_memory_and_refreshes_chrome() -> None:
    """Disabling compare mode should store disabled state and refresh presentation."""

    current = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )
    next_state = OutputCompareState(
        enabled=False,
        base=current.base,
        comparison=current.comparison,
    )
    presenter = _Presenter(disabled_state=next_state)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    sync_rendering_calls: list[None] = []
    tabbar_updates: list[None] = []
    controller = _controller(
        state=current,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
        sync_rendering_calls=sync_rendering_calls,
        tabbar_updates=tabbar_updates,
    )

    controller.set_compare_mode_enabled(False)

    assert presenter.disabled_calls == (current,)
    assert stored == [next_state]
    assert emitted == [next_state]
    assert sync_rendering_calls == [None]
    assert tabbar_updates == [None]


def test_set_compare_mode_enabled_ignores_missing_projection() -> None:
    """Enabling compare mode without a projection should not mutate visible state."""

    presenter = _Presenter()
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    controller = _controller(
        projection=None,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
    )

    controller.set_compare_mode_enabled(True)

    assert presenter.enabled_calls == ()
    assert stored == []
    assert emitted == []


def test_current_output_compare_selection_returns_active_concrete_route() -> None:
    """Current selection should be derived from active scene/source/set state."""

    controller = _controller(
        active_source_key="source-a",
        active_set_index=3,
        scene_count=2,
        active_scene_key="scene-b",
    )

    selection = controller.current_output_compare_selection()

    assert selection == OutputCompareSelection("scene-b", 3, "source-a")


def test_pane_comparison_change_stores_and_emits_changed_state() -> None:
    """QPane divider changes should update visible compare state exactly once."""

    current = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
        split_position=0.5,
    )
    changed = OutputCompareState(
        enabled=True,
        base=current.base,
        comparison=current.comparison,
        split_position=0.75,
    )
    presenter = _Presenter(qpane_state=changed)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    controller = _controller(
        state=current,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
    )
    payload = SimpleNamespace(split_position=0.75)

    controller.on_pane_comparison_changed(payload)

    assert presenter.qpane_calls == ((current, payload),)
    assert stored == [changed]
    assert emitted == [changed]


def test_pane_comparison_change_ignores_unchanged_state() -> None:
    """Unchanged QPane divider payloads should not emit compare updates."""

    current = OutputCompareState(enabled=True)
    presenter = _Presenter(qpane_state=current)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    controller = _controller(
        state=current,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
    )

    controller.on_pane_comparison_changed(object())

    assert stored == []
    assert emitted == []


def test_set_compare_selection_updates_base_route_and_refreshes_canvas() -> None:
    """Replacing base selection should update active route and refresh chrome."""

    current = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 1, "source-a"),
        comparison=OutputCompareSelection("scene-a", 1, "source-b"),
    )
    next_selection = OutputCompareSelection("scene-b", 3, "source-c")
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    active_scene_keys: list[str | None] = []
    active_source_keys: list[str] = []
    active_set_indexes: list[int] = []
    sync_calls: list[str] = []
    render_calls: list[None] = []
    tabbar_updates: list[None] = []
    controller = _controller(
        state=current,
        stored=stored,
        emitted=emitted,
        scene_count=2,
        active_scene_keys=active_scene_keys,
        active_source_keys=active_source_keys,
        active_set_indexes=active_set_indexes,
        sync_calls=sync_calls,
        sync_rendering_calls=render_calls,
        tabbar_updates=tabbar_updates,
    )

    controller.set_compare_selection("base", next_selection)

    expected = OutputCompareState(
        enabled=True,
        base=next_selection,
        comparison=current.comparison,
    )
    assert stored == [expected]
    assert emitted == [expected]
    assert active_scene_keys == ["scene-b"]
    assert active_source_keys == ["source-c"]
    assert active_set_indexes == [3]
    assert sync_calls == ["scene", "set", "source", "comparison"]
    assert render_calls == [None]
    assert tabbar_updates == [None]


def test_set_compare_source_updates_comparison_without_active_route_change() -> None:
    """Replacing comparison source should not move active base route state."""

    current = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )
    stored: list[OutputCompareState] = []
    active_source_keys: list[str] = []
    controller = _controller(
        state=current,
        stored=stored,
        active_source_keys=active_source_keys,
    )

    controller.set_compare_source("comparison", "source-c")

    assert stored == [
        OutputCompareState(
            enabled=True,
            base=current.base,
            comparison=OutputCompareSelection(None, 1, "source-c"),
        )
    ]
    assert active_source_keys == []


def test_compare_sources_for_selection_scopes_to_matching_scene() -> None:
    """Compare source lookup should use scene-local sources for scene projections."""

    scene_a_sources = (_source_with_item("source-a", "scene-a"),)
    scene_b_sources = (
        _source_with_item("source-b", "scene-b"),
        _source_with_item("source-c", "scene-b"),
    )
    projection = OutputCanvasProjection(
        sources=scene_a_sources + scene_b_sources,
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_count=2,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-a",
                scene_key="scene-a",
                title="Scene A",
                order=0,
                sources=scene_a_sources,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-b",
                scene_key="scene-b",
                title="Scene B",
                order=1,
                sources=scene_b_sources,
            ),
        ),
    )
    controller = _controller()

    sources = controller.compare_sources_for_selection(
        projection,
        OutputCompareSelection("scene-b", 1, "source-c"),
    )

    assert sources == scene_b_sources


def test_compare_projection_plan_defaults_base_and_counts_scoped_sources() -> None:
    """Compare projection sync should be planned from controller-owned policy."""

    scene_a_sources = (_source_with_item("source-a", "scene-a"),)
    scene_b_sources = (
        _source_with_item("source-b", "scene-b"),
        _source_with_item("source-c", "scene-b"),
    )
    projection = OutputCanvasProjection(
        sources=scene_a_sources + scene_b_sources,
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_count=2,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-a",
                scene_key="scene-a",
                title="Scene A",
                order=0,
                sources=scene_a_sources,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-b",
                scene_key="scene-b",
                title="Scene B",
                order=1,
                sources=scene_b_sources,
            ),
        ),
    )
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]] = []
    controller = _controller(counted_sources=counted_sources, set_count=4)

    plan = controller.compare_projection_plan(
        projection,
        OutputCompareState(enabled=True),
    )

    assert plan.state == OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 1, "source-a"),
        comparison=OutputCompareSelection("scene-b", 1, "source-c"),
    )
    assert plan.base == OutputCompareSelection("scene-a", 1, "source-a")
    assert plan.sources == scene_a_sources
    assert plan.set_count == 4
    assert counted_sources == [scene_a_sources]


def test_compare_set_count_uses_sources_for_active_side() -> None:
    """Compare set counts should be derived from the side-specific sources."""

    source_a = _source("source-a")
    source_b = _source("source-b")
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]] = []
    controller = _controller(
        projection=OutputCanvasProjection(
            sources=(source_a, source_b),
            active_source_key="source-a",
            active_set_index=1,
            active_uuid=None,
            set_count=2,
        ),
        state=state,
        counted_sources=counted_sources,
        set_count=7,
    )

    count = controller.compare_set_count("comparison")

    assert count == 7
    assert counted_sources == [(source_a, source_b)]


def test_compare_source_label_uses_selected_source_label() -> None:
    """Compare source labels should resolve from the selection's scoped sources."""

    source_a = _source("source-a", label="Base")
    source_b = _source("source-b", label="Comparison")
    controller = _controller(
        projection=OutputCanvasProjection(
            sources=(source_a, source_b),
            active_source_key="source-a",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        )
    )

    assert (
        controller.compare_source_label(OutputCompareSelection(None, 1, "source-b"))
        == "Comparison"
    )


def test_compare_source_label_falls_back_without_projection_or_source() -> None:
    """Compare source labels should have a stable empty-state fallback."""

    missing_projection = _controller(projection=None)
    missing_source = _controller(
        projection=OutputCanvasProjection(
            sources=(_source("source-a", label="Base"),),
            active_source_key="source-a",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        )
    )

    assert (
        missing_projection.compare_source_label(
            OutputCompareSelection(None, 1, "source-a")
        )
        == "Output"
    )
    assert (
        missing_source.compare_source_label(
            OutputCompareSelection(None, 1, "source-missing")
        )
        == "Output"
    )


def test_compare_buttons_return_side_specific_widget_objects() -> None:
    """Compare button helpers should resolve base and comparison controls by side."""

    buttons = _Buttons()
    controller = _controller(buttons=buttons)

    assert controller.compare_scene_button("base") is buttons.base_scene
    assert controller.compare_scene_button("comparison") is buttons.comparison_scene
    assert controller.compare_set_button("base") is buttons.base_set
    assert controller.compare_set_button("comparison") is buttons.comparison_set
    assert controller.compare_source_button("base") is buttons.base_source
    assert controller.compare_source_button("comparison") is buttons.comparison_source


def test_compare_source_picker_row_width_uses_widest_label() -> None:
    """Compare source row width should honor the minimum and measured labels."""

    measured: list[str] = []
    controller = _controller(
        source_width_for_text=lambda text: _record_width(measured, text),
        source_selector_min_width=44,
    )

    width = controller.compare_source_picker_row_width(
        (
            _PickerItem("A"),
            _PickerItem("Long label"),
        )
    )

    assert width == 100
    assert measured == ["A", "Long label"]


@dataclass(slots=True)
class _Presenter:
    """Record compare-state presenter calls and return configured states."""

    enabled_state: OutputCompareState = OutputCompareState(enabled=True)
    disabled_state: OutputCompareState = OutputCompareState(enabled=False)
    qpane_state: OutputCompareState = OutputCompareState(enabled=True)
    enabled_calls: tuple[
        tuple[OutputCanvasProjection, OutputCompareSelection | None],
        ...,
    ] = ()
    disabled_calls: tuple[OutputCompareState, ...] = ()
    qpane_calls: tuple[tuple[OutputCompareState, object], ...] = ()

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

    def state_from_qpane_change(
        self,
        state: OutputCompareState,
        qpane_state: object,
    ) -> OutputCompareState:
        """Return configured QPane state and record the payload."""

        self.qpane_calls = (*self.qpane_calls, (state, qpane_state))
        return self.qpane_state


@dataclass(frozen=True, slots=True)
class _Buttons:
    """Hold opaque button objects for compare controller tests."""

    base_scene: object = object()
    comparison_scene: object = object()
    base_set: object = object()
    comparison_set: object = object()
    base_source: object = object()
    comparison_source: object = object()


@dataclass(frozen=True, slots=True)
class _PickerItem:
    """Expose a picker label for row-width tests."""

    label: str


def _controller(
    *,
    projection: OutputCanvasProjection | None = None,
    state: OutputCompareState | None = None,
    presenter: _Presenter | None = None,
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
    buttons: _Buttons | None = None,
    source_width_for_text: Callable[[str], int] | None = None,
    source_selector_min_width: int = 20,
    active_source_key: str | None = "source-a",
    active_set_index: int = 1,
    scene_count: int = 1,
    active_scene_key: str | None = None,
) -> OutputCompareController:
    """Return a compare controller with deterministic collaborators."""

    active_state = state or OutputCompareState()
    active_presenter = presenter or _Presenter()
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
    active_buttons = buttons or _Buttons()
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
        set_count_for_sources=lambda sources: _record_sources(
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


def _projection() -> OutputCanvasProjection:
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


def _source(source_key: str, *, label: str | None = None) -> OutputCanvasSourceGroup:
    """Return a source group identified by key for controller tests."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=label or source_key,
        images_by_set={},
    )


def _source_with_item(source_key: str, scene_key: str) -> OutputCanvasSourceGroup:
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


def _record_sources(
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]],
    sources: tuple[OutputCanvasSourceGroup, ...],
    count: int,
) -> int:
    """Record source-count input and return configured count."""

    counted_sources.append(sources)
    return count


def _record_width(measured: list[str], text: str) -> int:
    """Record measured text and return deterministic label width."""

    measured.append(text)
    return 100 if text == "Long label" else 12
