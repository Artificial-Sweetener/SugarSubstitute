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

"""Tests for WorkspaceController generation binding facade behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.workspace_controller_test_support import import_workspace_controller_module


def test_generation_bindings_route_feedback_through_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace generation bindings should not target direct MainWindow UI methods."""

    mod = import_workspace_controller_module(monkeypatch)
    controller = object.__new__(mod.WorkspaceController)
    dispatcher = SimpleNamespace(
        on_run_started=lambda _event: None,
        on_progress=lambda _progress: None,
        on_model_load_progress=lambda _progress: None,
        on_preview=lambda _preview: None,
        on_output_image=lambda _output: None,
        on_failure=lambda _failure: None,
        on_timing=lambda _timing: None,
        on_completed=lambda _workflow_id: None,
    )
    view = SimpleNamespace(
        generation_feedback_dispatcher=dispatcher,
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        _randomize_active_seed_boxes=lambda: None,
        _request_clear_output_for_workflow=lambda _workflow_id: None,
    )
    controller._views = SimpleNamespace(generation=view)
    controller._collaborators = SimpleNamespace(
        generation_seed_randomizer=lambda *, request, behavior_snapshot: None
    )
    controller.build_generation_request = lambda: None
    controller.build_queued_generation_snapshots = lambda: ()

    bindings = mod.WorkspaceController.build_generation_bindings(controller)

    assert bindings.on_progress is dispatcher.on_progress
    assert bindings.on_run_started is dispatcher.on_run_started
    assert bindings.on_model_load_progress is dispatcher.on_model_load_progress
    assert bindings.on_preview is dispatcher.on_preview
    assert bindings.on_output_image is dispatcher.on_output_image
    assert bindings.on_failure is dispatcher.on_failure
    assert bindings.on_completed is dispatcher.on_completed


def test_generation_bindings_use_registry_batch_count_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared titlebar control registry should own generated batch count."""

    mod = import_workspace_controller_module(monkeypatch)
    controller = object.__new__(mod.WorkspaceController)
    dispatcher = SimpleNamespace(
        on_run_started=lambda _event: None,
        on_progress=lambda _progress: None,
        on_model_load_progress=lambda _progress: None,
        on_preview=lambda _preview: None,
        on_output_image=lambda _output: None,
        on_failure=lambda _failure: None,
        on_timing=lambda _timing: None,
        on_completed=lambda _workflow_id: None,
    )
    view = SimpleNamespace(
        generation_feedback_dispatcher=dispatcher,
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: None
        ),
        generation_titlebar_control_registry=SimpleNamespace(
            effective_batch_count=lambda: 5
        ),
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 2),
        _randomize_active_seed_boxes=lambda: None,
        _request_clear_output_for_workflow=lambda _workflow_id: None,
    )
    controller._views = SimpleNamespace(generation=view)
    controller._collaborators = SimpleNamespace(
        generation_seed_randomizer=lambda *, request, behavior_snapshot: None
    )
    controller.build_generation_request = lambda: None
    controller.build_queued_generation_snapshots = lambda: ()

    bindings = mod.WorkspaceController.build_generation_bindings(controller)

    assert bindings.effective_batch_count() == 5
