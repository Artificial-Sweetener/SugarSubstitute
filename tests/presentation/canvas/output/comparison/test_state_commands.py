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

"""Verify Output comparison state and command orchestration."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    store_visible_output_compare_state,
    visible_output_compare_state,
)


from tests.presentation.canvas.output.comparison.controller_support import (
    PresenterSpy,
    build_controller,
    build_projection,
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

    projection = build_projection()
    next_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 2, "source-a"),
        comparison=OutputCompareSelection("scene-a", 2, "source-b"),
    )
    presenter = PresenterSpy(enabled_state=next_state)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    synced: list[tuple[OutputCanvasProjection, OutputCompareState]] = []
    controller = build_controller(
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
    presenter = PresenterSpy(disabled_state=next_state)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    sync_rendering_calls: list[None] = []
    tabbar_updates: list[None] = []
    controller = build_controller(
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

    presenter = PresenterSpy()
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    controller = build_controller(
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

    controller = build_controller(
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
    presenter = PresenterSpy(presentation_state=changed)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    controller = build_controller(
        state=current,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
    )
    payload = SimpleNamespace(split_position=0.75)

    controller.on_workspace_presentation_changed(payload)

    assert presenter.presentation_calls == ((current, payload),)
    assert stored == [changed]
    assert emitted == [changed]


def test_workspace_presentation_change_ignores_unchanged_state() -> None:
    """Unchanged workspace divider payloads should not emit compare updates."""

    current = OutputCompareState(enabled=True)
    presenter = PresenterSpy(presentation_state=current)
    stored: list[OutputCompareState] = []
    emitted: list[OutputCompareState] = []
    controller = build_controller(
        state=current,
        presenter=presenter,
        stored=stored,
        emitted=emitted,
    )

    controller.on_workspace_presentation_changed(object())

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
    controller = build_controller(
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
    controller = build_controller(
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
