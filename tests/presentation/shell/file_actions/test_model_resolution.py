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

"""Test recipe model acquisition before materialization."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast


from tests.presentation.shell.file_actions.support import (
    _import_module,
    _append,
    _append_then,
    _EditorBusyRecorder,
    _QueuedRuntimeSubmitter,
    _QueuedExecutionRuntime,
    _noop_output_registrar,
    _TabItem,
    _CubeStack,
    _EditorPanel,
)


def test_recipe_model_resolution_uses_injected_runner_before_materialization() -> None:
    """Pre-materialization model resolution should go through the runner boundary."""

    mod = _import_module()
    runner_calls: list[object] = []
    parsed_script = SimpleNamespace()
    resolved_payload = SimpleNamespace(
        parsed_script=parsed_script,
        summary=SimpleNamespace(
            literal_matches=0,
            hash_matches=0,
            unresolved_hashes=0,
        ),
    )

    class _Resolver:
        """Fail if direct resolution bypasses the injected runner."""

        def resolve(self, parsed: object) -> object:
            """Direct calls are not expected in this contract test."""

            raise AssertionError(f"Resolver should run through runner, got {parsed!r}.")

    def runner(resolver_factory: object, parsed: object) -> object:
        """Record that resolution crossed the runner boundary."""

        runner_calls.append(parsed)
        assert callable(resolver_factory)
        assert parsed is parsed_script
        return resolved_payload

    actions = mod.WorkspaceFileActions(
        SimpleNamespace(),
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=_noop_output_registrar(),
        recipe_model_resolution_runner=runner,
    )

    result = actions._resolve_recipe_model_references(
        resolver_factory=lambda: _Resolver(),
        parsed_script=cast(Any, parsed_script),
    )

    assert result is resolved_payload
    assert runner_calls == [parsed_script]


def test_recipe_model_resolution_handler_can_supply_downloaded_script() -> None:
    """Missing model handler results should unblock materialization with its script."""

    mod = _import_module()
    from substitute.application.recipes import (  # noqa: PLC0415
        RecipeModelCivitaiState,
        RecipeModelResolutionRequired,
        RecipeModelResolutionSummary,
        RecipeModelUnresolvedReference,
    )

    parsed_script = SimpleNamespace()
    handled_payload = SimpleNamespace(
        parsed_script=parsed_script,
        summary=SimpleNamespace(
            literal_matches=0,
            hash_matches=1,
            unresolved_hashes=0,
        ),
    )
    required = RecipeModelResolutionRequired(
        references=(
            RecipeModelUnresolvedReference(
                alias="A",
                node_name="checkpoint",
                input_key="ckpt_name",
                kind="checkpoints",
                value="missing.safetensors",
                sha256="A" * 64,
                civitai_state=RecipeModelCivitaiState.FOUND,
            ),
        ),
        partial_script=cast(Any, parsed_script),
        summary=RecipeModelResolutionSummary(unresolved_hashes=1),
    )

    def runner(_resolver_factory: object, _parsed: object) -> object:
        """Simulate a resolver worker that found missing CivitAI models."""

        raise required

    actions = mod.WorkspaceFileActions(
        SimpleNamespace(),
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=_noop_output_registrar(),
        recipe_model_resolution_runner=runner,
        recipe_model_resolution_handler=lambda error: (
            handled_payload if error is required else None
        ),
    )

    result = actions._resolve_recipe_model_references(
        resolver_factory=lambda: object(),
        parsed_script=cast(Any, parsed_script),
    )

    assert result is handled_payload


def test_recipe_model_resolution_runtime_continues_materialization_after_completion(
    tmp_path: Path,
) -> None:
    """Runtime-backed recipe model resolution should defer workflow materialization."""

    mod = _import_module()
    workflow_id = "wf-a"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    submitter = _QueuedRuntimeSubmitter()
    runtime = _QueuedExecutionRuntime(submitter)
    calls: list[object] = []
    loader_calls: list[dict[str, object]] = []
    parsed_script = SimpleNamespace(
        buffers={"A": {"cube_id": "cube-a"}},
        global_overrides={"seed": 1},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        project_name="Resolved Recipe",
    )
    resolved_script = SimpleNamespace(
        parsed_script=parsed_script,
        summary=SimpleNamespace(
            literal_matches=1,
            hash_matches=1,
            unresolved_hashes=0,
        ),
    )

    class _Resolver:
        """Resolve the parsed script when the queued task is run."""

        def resolve(self, parsed: object) -> object:
            """Return the resolved script payload."""

            calls.append(("resolve", parsed))
            return resolved_script

    workflow = SimpleNamespace(
        stack_order=[],
        cubes={},
        global_overrides={},
        global_override_selections={},
        override_control_states={},
    )
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows={workflow_id: workflow},
            get_workflow=lambda current_id: (
                workflow if current_id == workflow_id else None
            ),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=tmp_path / "recipe.sugar",
                    source_kind="sugar",
                ),
                parsed_script=parsed_script,
            )
        ),
        create_recipe_model_load_resolver=lambda: _Resolver(),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=SimpleNamespace(
            apply_global_overrides=lambda: calls.append("overrides")
        ),
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path,
            cubes_dir=tmp_path,
        ),
        editor_busy=_EditorBusyRecorder(calls),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: calls.append("new-workflow"),
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=_noop_output_registrar(),
        recipe_model_resolution_route_factory=(
            lambda request_id, target_workflow_id: mod.RecipeModelResolutionRoute(
                submitter=runtime.submitter(
                    "recipe_model_resolution",
                    owner_id=(
                        f"recipe_model_resolution_{target_workflow_id}_{request_id}"
                    ),
                    dispatcher=object(),
                ),
                close=submitter.close,
            )
        ),
    )

    opened_id = actions.load_recipe_document(
        tmp_path / "recipe.sugar",
        projects_dir=tmp_path,
        icon_provider=SimpleNamespace(CLOSE=SimpleNamespace(icon=lambda: "icon")),
        cube_loader=lambda callbacks, **kwargs: loader_calls.append(
            {"callbacks": callbacks, **kwargs}
        ),
    )

    assert opened_id == workflow_id
    assert runtime.calls[0][0] == "recipe_model_resolution"
    assert loader_calls == []
    assert submitter.cancellations[0].generation > 0
    assert (
        submitter.requests[0].identity.cancellation_generation
        == submitter.cancellations[0].generation
    )
    result = submitter.requests[0].work(submitter.cancellations[0])
    submitter.handles[0].complete_success(result)

    assert calls[0] == ("resolve", parsed_script)
    assert loader_calls[0]["cube_id"] == "cube-a"
    assert tab_item.text() == "Resolved Recipe"
    assert not submitter.cancellations[0].is_cancelled
    assert submitter.closed is True


def test_downloaded_recipe_model_refreshes_node_definition_choices() -> None:
    """Applying a downloaded model should force-refresh stale picker option lists."""

    mod = _import_module()
    refreshed_classes: list[str] = []
    override_calls: list[str] = []
    workflow_id = "wf-a"
    downloaded_buffer = {
        "nodes": {
            "loader": {
                "inputs": {"diffusion_model": "anima_baseV10.safetensors"},
            }
        }
    }
    runtime_buffer = {
        "nodes": {
            "loader": {
                "class_type": "SimpleSyrup.SimpleLoadAnima",
                "inputs": {"diffusion_model": "preview3-base.safetensors"},
            }
        },
        "runtime_only": True,
    }
    workflow = SimpleNamespace(
        cubes={"A": SimpleNamespace(buffer=runtime_buffer)},
        global_overrides={},
        global_override_selections={},
    )
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows={workflow_id: workflow},
        ),
        editor_panels={},
        active_override_manager=SimpleNamespace(
            sync_state_from_workflow=lambda: _append(override_calls, "sync"),
            apply_global_overrides=lambda: _append(override_calls, "apply"),
        ),
        node_definition_gateway=SimpleNamespace(
            refresh_node_definition=lambda node_class: _append_then(
                refreshed_classes,
                node_class,
                {node_class: {"input": {}}},
            )
        ),
    )
    request = mod.DeferredRecipeModelDownload(
        service=object(),
        required=SimpleNamespace(
            references=(
                SimpleNamespace(
                    alias="A",
                    node_name="loader",
                    input_key="diffusion_model",
                ),
            )
        ),
        api_key_override=None,
    )
    parsed_script = SimpleNamespace(
        buffers={"A": downloaded_buffer},
        global_overrides={"diffusion_model": {"value": "anima_baseV10.safetensors"}},
        global_override_selections={},
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=_noop_output_registrar(),
    )

    actions._apply_downloaded_recipe_models(
        resolved_script=SimpleNamespace(parsed_script=parsed_script),
        request=request,
        target_workflow_id=workflow_id,
    )

    assert workflow.cubes["A"].buffer is runtime_buffer
    assert runtime_buffer["runtime_only"] is True
    assert runtime_buffer["nodes"]["loader"]["inputs"] == {
        "diffusion_model": "anima_baseV10.safetensors"
    }
    assert refreshed_classes == ["SimpleSyrup.SimpleLoadAnima"]
    assert override_calls == ["sync", "apply"]


def test_recipe_model_download_message_uses_backend_destination_detail() -> None:
    """Running download copy should show the exact backend-reported destination."""

    mod = _import_module()
    message = mod._recipe_model_download_message(
        mod.BackendModelDownloadJob(
            job_id="job-a",
            status=mod.ModelDownloadStatus.RUNNING,
            kind="diffusion_models",
            sha256="A" * 64,
            value=None,
            result=None,
            error=None,
            detail=r"Saving to E:\ImageGen Models\diffusion_models\Anima.safetensors",
        ),
        model_label="Anima",
    )

    assert message == r"Saving to E:\ImageGen Models\diffusion_models\Anima.safetensors"
