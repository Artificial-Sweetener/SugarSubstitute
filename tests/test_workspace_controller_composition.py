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

"""Tests for workspace controller collaborator composition."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.generation import SeedRandomizationResult, SeedValueChange
from substitute.presentation.shell import workspace_controller_composition as mod


class _FakeWorkflowWorkspaceCoordinator:
    """Record workflow workspace construction."""

    def __init__(self, view: object) -> None:
        """Store the view and expose an add workflow callback."""

        self.view = view
        self.added: list[object] = []

    def add_workflow(self, workflow: object = None) -> None:
        """Record workflow-add callback use."""

        self.added.append(workflow)


class _FakeAction:
    """Capture collaborator constructor arguments."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Store constructor arguments for assertions."""

        self.args: tuple[object, ...] = args
        self.kwargs: dict[str, object] = kwargs
        self.added_outputs: list[tuple[object, object, object]] = []
        self.loaded_outputs: list[tuple[object, object, object]] = []

    def handle_add_output_image(
        self,
        workflow_id: object,
        image: object,
        image_meta: object,
    ) -> None:
        """Record generated-output registrations."""

        self.added_outputs.append((workflow_id, image, image_meta))

    def handle_loaded_output_image(
        self,
        workflow_id: object,
        image: object,
        image_meta: object,
    ) -> None:
        """Record loaded-output registrations."""

        self.loaded_outputs.append((workflow_id, image, image_meta))


class _FakeSeedRandomizationService:
    """Stand in for the application seed-randomization service."""


class _FakeSeedValueProjector:
    """Record authoritative seed projections composed for generation."""

    calls: list[tuple[object, SeedRandomizationResult]] = []

    def __init__(self, _view: object) -> None:
        """Accept the generation view used by production composition."""

    def project(self, workflow: object, result: SeedRandomizationResult) -> None:
        """Record one model-to-widget seed projection."""

        self.calls.append((workflow, result))


def test_compose_workspace_controller_collaborators_builds_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Composition should wire controller collaborators without controller fields."""

    seed_calls: list[dict[str, object]] = []

    def randomize_generation_request_seeds(
        **kwargs: object,
    ) -> SeedRandomizationResult:
        """Record seed-randomization adapter inputs."""

        seed_calls.append(kwargs)
        return SeedRandomizationResult(
            (SeedValueChange(value=42, previous_value=7, override_key="seed"),)
        )

    monkeypatch.setattr(
        mod,
        "WorkflowWorkspaceCoordinator",
        _FakeWorkflowWorkspaceCoordinator,
    )
    monkeypatch.setattr(mod, "WorkflowDuplicateService", lambda: "duplicate-service")
    monkeypatch.setattr(mod, "WorkspaceCanvasActions", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceCubePickerActions", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceCubeStackActions", _FakeAction)
    monkeypatch.setattr(mod, "DeferredCubeDuplicationLinkReconciler", _FakeAction)
    monkeypatch.setattr(mod, "ActiveWorkflowSurfaceRefresher", _FakeAction)
    monkeypatch.setattr(mod, "CubeDuplicationService", _FakeAction)
    monkeypatch.setattr(mod, "CubeStackPresenter", _FakeAction)
    monkeypatch.setattr(mod, "CubeTabIconResolver", _FakeAction)
    monkeypatch.setattr(mod, "CubeSurfaceProjectionCoordinator", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceFileActions", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceSearchActions", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceGenerationActions", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceSceneGenerationActions", _FakeAction)
    monkeypatch.setattr(mod, "WorkspaceLoadedCubeSurfaceActions", _FakeAction)
    monkeypatch.setattr(mod, "SeedRandomizationService", _FakeSeedRandomizationService)
    _FakeSeedValueProjector.calls.clear()
    monkeypatch.setattr(mod, "SeedValueProjector", _FakeSeedValueProjector)
    monkeypatch.setattr(
        mod,
        "randomize_generation_request_seeds",
        randomize_generation_request_seeds,
    )

    host = SimpleNamespace(
        _error_presenter="errors",
        recipe_output_sibling_discovery_service="siblings",
        shell_recipe_model_resolution_controller=SimpleNamespace(
            resolve_missing_recipe_models="resolver"
        ),
    )
    autosave_calls: list[str] = []
    views = mod.WorkspaceControllerViews(
        generation=cast(
            Any,
            SimpleNamespace(
                name="generation",
                request_session_autosave=lambda: autosave_calls.append("autosave"),
            ),
        ),
        workflow_workspace=cast(Any, SimpleNamespace(name="workflow-workspace")),
        file=cast(Any, SimpleNamespace(name="file")),
        cube=cast(
            Any,
            SimpleNamespace(
                name="cube",
                node_behavior_service="node-behavior",
                cube_stack_service="cube-stack-service",
                cube_icon_factory="cube-icon-factory",
                active_workflow_surface_refresher="surface-refresher",
            ),
        ),
        canvas=cast(Any, SimpleNamespace(name="canvas")),
        search=cast(Any, SimpleNamespace(name="search")),
    )
    build_cube_load_ui_callbacks = cast(Any, lambda **_kwargs: "cube-callbacks")
    build_generation_bindings = cast(Any, lambda: "generation-bindings")
    build_scene_generation_snapshot = cast(
        Any,
        lambda scene_key: f"scene:{scene_key}",
    )
    scene_preflight_error = cast(Any, lambda **kwargs: RuntimeError(kwargs))

    bundle = mod.compose_workspace_controller_collaborators(
        host=host,
        views=views,
        build_cube_load_ui_callbacks=build_cube_load_ui_callbacks,
        materialize_loaded_cube_input_canvas=lambda *_args: None,
        build_generation_bindings=build_generation_bindings,
        build_scene_generation_snapshot=build_scene_generation_snapshot,
        scene_generation_preflight_error=scene_preflight_error,
    )

    workflow_workspace = cast(
        _FakeWorkflowWorkspaceCoordinator, bundle.workflow_workspace
    )
    canvas_actions = cast(_FakeAction, bundle.canvas_actions)
    cube_picker_actions = cast(_FakeAction, bundle.cube_picker_actions)
    cube_stack_actions = cast(_FakeAction, bundle.cube_stack_actions)
    file_actions = cast(_FakeAction, bundle.file_actions)
    search_actions = cast(_FakeAction, bundle.search_actions)
    generation_actions = cast(_FakeAction, bundle.generation_actions)
    scene_generation_actions = cast(_FakeAction, bundle.scene_generation_actions)
    loaded_cube_surface_actions = cast(_FakeAction, bundle.loaded_cube_surface_actions)

    assert isinstance(workflow_workspace, _FakeWorkflowWorkspaceCoordinator)
    assert workflow_workspace.view is views.workflow_workspace
    assert cast(object, bundle.workflow_duplicate_service) == "duplicate-service"
    assert canvas_actions.args == (views.canvas,)
    assert canvas_actions.kwargs["error_presenter"] == "errors"
    assert cube_picker_actions.args == (views.cube,)
    assert cube_picker_actions.kwargs["build_cube_load_ui_callbacks"] is (
        build_cube_load_ui_callbacks
    )
    assert cube_stack_actions.args == (views.cube,)
    assert file_actions.args == (views.file,)
    add_workflow_tab_requested = cast(
        Any,
        file_actions.kwargs["add_workflow_tab_requested"],
    )
    add_workflow_tab_requested()
    assert workflow_workspace.added == [None]
    assert file_actions.kwargs["recipe_output_sibling_discovery_service"] == "siblings"
    assert file_actions.kwargs["recipe_model_resolution_handler"] == "resolver"
    assert callable(file_actions.kwargs["recipe_model_resolution_route_factory"])
    assert callable(file_actions.kwargs["recipe_model_download_route_factory"])
    output_registrar = cast(Any, file_actions.kwargs["output_image_registrar"])
    output_registrar.add_output_image("wf-a", "image-a", "meta-a")
    assert canvas_actions.loaded_outputs == [("wf-a", "image-a", "meta-a")]
    assert canvas_actions.added_outputs == []
    assert search_actions.args == (views.search,)
    assert generation_actions.args == (views.generation,)
    assert generation_actions.kwargs["build_generation_bindings"] is (
        build_generation_bindings
    )
    assert scene_generation_actions.args == (views.generation,)
    assert scene_generation_actions.kwargs["build_scene_snapshot"] is (
        build_scene_generation_snapshot
    )
    assert loaded_cube_surface_actions.kwargs["cube_view"] is views.cube
    assert loaded_cube_surface_actions.kwargs["workflow_workspace"] is (
        workflow_workspace
    )

    workflow = object()
    request = SimpleNamespace(name="request", workflow=workflow)
    behavior_snapshot = SimpleNamespace(name="snapshot")
    assert bundle.generation_seed_randomizer(
        request=request,
        behavior_snapshot=behavior_snapshot,
    )
    assert len(seed_calls) == 1
    assert seed_calls[0]["request"] is request
    assert seed_calls[0]["behavior_snapshot"] is behavior_snapshot
    assert isinstance(
        seed_calls[0]["seed_randomization_service"],
        _FakeSeedRandomizationService,
    )
    assert _FakeSeedValueProjector.calls == [
        (
            workflow,
            SeedRandomizationResult(
                (SeedValueChange(value=42, previous_value=7, override_key="seed"),)
            ),
        )
    ]
    assert autosave_calls == ["autosave"]


def test_workspace_controller_composition_does_not_import_controller() -> None:
    """Composition module must not depend on the concrete workspace controller."""

    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "workspace_controller import" not in source


def test_cube_load_execution_routes_use_unique_owners_for_shared_trace() -> None:
    """Concurrent staged loads may share one trace without sharing a dispatcher."""

    class _Submitter:
        """Provide the close surface required by a cube-load route."""

        def close(self) -> None:
            """Close the fake submitter."""

    class _ExecutionRuntime:
        """Reject duplicate runtime owner identities like production does."""

        def __init__(self) -> None:
            """Create empty dispatcher ownership state."""

            self.owner_ids: list[str] = []

        def submitter(
            self,
            name: str,
            *,
            owner_id: str,
            dispatcher: object,
        ) -> _Submitter:
            """Record one uniquely owned cube-load submitter."""

            _ = dispatcher
            assert name == "cube_load"
            if owner_id in self.owner_ids:
                raise RuntimeError(f"duplicate execution owner: {owner_id}")
            self.owner_ids.append(owner_id)
            return _Submitter()

    execution_runtime = _ExecutionRuntime()
    host = SimpleNamespace(execution_runtime=execution_runtime)

    first_route = mod._cube_load_execution_route(
        host=host,
        cube_load_trace_id="shared-batch-trace",
    )
    second_route = mod._cube_load_execution_route(
        host=host,
        cube_load_trace_id="shared-batch-trace",
    )

    assert first_route is not second_route
    assert len(execution_runtime.owner_ids) == 2
    assert len(set(execution_runtime.owner_ids)) == 2
    assert all(
        owner_id.startswith("cube_load_shared-batch-trace_")
        for owner_id in execution_runtime.owner_ids
    )
