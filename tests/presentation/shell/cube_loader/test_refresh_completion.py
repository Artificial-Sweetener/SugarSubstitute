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

"""Test cube-loader refresh completion contracts."""

from __future__ import annotations

from collections.abc import Callable
import pytest

from .support import (
    _FakeQTimer,
    _build_loader_state,
    _import_cube_loader_module,
    _stub_cube_service,
)


def test_load_cube_async_can_refresh_without_revealing_for_batch_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch loads should refresh inserted cubes and defer activation/reveal."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    refresh_only_calls: list[tuple[str, str]] = []
    finished_aliases: list[str | None] = []

    def refresh_loaded_surface(workflow_id: str, alias: str, **_kwargs: object) -> bool:
        """Record the silent refresh requested for this staged load."""

        refresh_only_calls.append((workflow_id, alias))
        return True

    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        refresh_loaded_cube_surface=refresh_loaded_surface,
        cube_load_execution_route_factory=callbacks.cube_load_execution_route_factory,
        schedule_next_gui_turn=callbacks.schedule_next_gui_turn,
    )

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        reveal_after_load=False,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_all()

    assert refresh_calls == []
    assert refresh_only_calls == [("wfA", "Alias1")]
    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]
    assert state.editor_panels["wfA"].reveal_calls == []


def test_load_cube_async_waits_for_async_editor_refresh_before_finishing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube-load completion should wait for progressive editor build completion."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    refresh_completions: list[Callable[[], None]] = []
    finished_aliases: list[str | None] = []

    def refresh_async(workflow_id: str, alias: str, done: Callable[[], None]) -> None:
        """Record the async refresh request and hold completion for assertions."""

        refresh_calls.append((workflow_id, alias))
        refresh_completions.append(done)

    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        refresh_workflow_after_cube_load_async=refresh_async,
        cube_load_execution_route_factory=callbacks.cube_load_execution_route_factory,
        schedule_next_gui_turn=callbacks.schedule_next_gui_turn,
    )

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_next()
    _FakeQTimer.run_next()

    assert refresh_calls == [("wfA", "Alias1")]
    assert refresh_completions
    assert materialized == []
    assert finished_aliases == []

    refresh_completions.pop()()
    _FakeQTimer.run_all()

    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]


def test_load_cube_async_finishes_after_silent_async_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silent staged loads should continue after async editor insertion completes."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    refresh_completions: list[Callable[[bool], None]] = []
    refresh_kwargs: list[dict[str, object]] = []
    finished_aliases: list[str | None] = []

    def refresh_async(
        workflow_id: str,
        alias: str,
        done: Callable[[bool], None],
        **kwargs: object,
    ) -> None:
        """Record the silent async refresh request and hold completion."""

        refresh_calls.append((workflow_id, alias))
        refresh_kwargs.append(kwargs)
        refresh_completions.append(done)

    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        refresh_loaded_cube_surface_async=refresh_async,
        cube_load_execution_route_factory=callbacks.cube_load_execution_route_factory,
        schedule_next_gui_turn=callbacks.schedule_next_gui_turn,
    )

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        reveal_after_load=False,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_next()
    _FakeQTimer.run_next()

    assert refresh_calls == [("wfA", "Alias1")]
    assert refresh_kwargs == [{"wait_for_complete": True}]
    assert materialized == []

    refresh_completions.pop()(True)
    _FakeQTimer.run_all()

    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]
