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

"""Test cube-loader worker handoff contracts."""

from __future__ import annotations

from typing import Any
import pytest

from .execution_support import _QueuedSubmitter, _route_factory, _with_submitter
from .support import (
    _FakeQTimer,
    _build_loader_state,
    _import_cube_loader_module,
    _stub_cube_service,
)


def test_load_cube_async_defers_runtime_build_to_second_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Definition completion should queue valid identifier text to a second worker."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, _materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service(graph={"nodes": {"n1": {}}})
    runtime_builds: list[str] = []
    original_build_loaded_cube_runtime = service.build_loaded_cube_runtime

    def _build_loaded_cube_runtime(*args: Any, **kwargs: Any) -> Any:
        runtime_builds.append("runtime")
        return original_build_loaded_cube_runtime(*args, **kwargs)

    service.build_loaded_cube_runtime = _build_loaded_cube_runtime
    callbacks = build_callbacks(service)
    submitter = _QueuedSubmitter()
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
        cube_load_execution_route_factory=_route_factory(module, submitter),
    )

    module.load_cube_async(
        callbacks,
        cube_id=("Artificial-Sweetener/Base-Cubes/Anima/Promptmask Detailer.cube"),
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    assert len(submitter.items) == 1
    submitter.run_next()
    assert runtime_builds == []
    assert len(submitter.items) == 1
    submitter.run_next()
    _FakeQTimer.run_all()

    assert runtime_builds == ["runtime"]
    loaded_cube = state.workflow_session_service.workflows["wfA"].cubes["Alias1"]
    assert loaded_cube.cube_id == (
        "Artificial-Sweetener/Base-Cubes/Anima/Promptmask Detailer.cube"
    )


def test_load_cube_async_scopes_worker_cancellation_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube-load workers should receive owner-scoped cancellation generations."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, _materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}})),
            submitter,
        ),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    definition_request, definition_token, _definition_handle = submitter.items[0]
    assert definition_token.generation > 0
    assert (
        definition_request.identity.cancellation_generation
        == definition_token.generation
    )

    submitter.run_next()
    runtime_request, runtime_token, _runtime_handle = submitter.items[0]
    assert runtime_token.generation > definition_token.generation
    assert runtime_request.identity.cancellation_generation == runtime_token.generation

    submitter.run_next()
    _FakeQTimer.run_all()

    assert not definition_token.is_cancelled
    assert not runtime_token.is_cancelled
    assert "Alias1" in state.workflow_session_service.workflows["wfA"].cubes


def test_load_cube_async_splits_ui_handoff_across_timer_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loaded cube UI refresh should yield between owned GUI commit phases."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()
    finished_aliases: list[str | None] = []

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}})),
            submitter,
        ),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )

    submitter.run_next()
    submitter.run_next()

    assert len(_FakeQTimer.queue) == 1
    _FakeQTimer.run_next()
    assert refresh == []
    assert materialized == []
    assert finished_aliases == []

    _FakeQTimer.run_next()
    assert refresh == [("wfA", "Alias1")]
    assert materialized == []
    assert finished_aliases == []

    _FakeQTimer.run_next()
    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == []

    _FakeQTimer.run_next()
    assert finished_aliases == ["Alias1"]
