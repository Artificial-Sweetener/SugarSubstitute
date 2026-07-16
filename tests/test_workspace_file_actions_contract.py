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

"""Contract tests for extracted workspace file actions."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, TypeVar, cast

from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.execution_testing import ManualTaskHandle

ValueT = TypeVar("ValueT")
ReturnT = TypeVar("ReturnT")
TaskResultT = TypeVar("TaskResultT")


def _import_module() -> ModuleType:
    """Import the workspace file actions module."""

    return importlib.import_module(
        "substitute.presentation.shell.workspace_file_actions"
    )


def _append(values: list[ValueT], value: ValueT) -> None:
    """Append one value from callback doubles that should return None."""

    values.append(value)


def _append_then(
    values: list[ValueT],
    value: ValueT,
    result: ReturnT,
) -> ReturnT:
    """Append one callback value and return the requested test double result."""

    values.append(value)
    return result


class _EditorBusyRecorder:
    """Record editor busy controller calls for file action tests."""

    def __init__(self, calls: list[object] | None = None) -> None:
        """Store the optional call list."""

        self._calls = calls

    def begin(self, workflow_id: str, *, message: str = "Loading") -> object:
        """Record a begin request and return a stable token."""

        if self._calls is not None:
            self._calls.append(("begin", (workflow_id, message)))
        return "busy-token"

    def end(self, token: object) -> None:
        """Record an end request."""

        if self._calls is not None:
            self._calls.append(("end", token))

    def set_cancel_callback(self, _token: object, _callback: object) -> None:
        """Accept cancel callback updates for download tests."""

    def update_download(self, _token: object, _state: object) -> None:
        """Accept download progress updates for download tests."""


class _QueuedRuntimeSubmitter:
    """Capture one runtime task for deterministic completion in tests."""

    def __init__(self) -> None:
        """Create empty submission state."""

        self.requests: list[TaskRequest[object]] = []
        self.handles: list[ManualTaskHandle[object]] = []
        self.cancellations: list[CancellationToken] = []
        self.closed = False

    def submit(
        self,
        request: TaskRequest[TaskResultT],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TaskResultT]:
        """Queue one request and return a manual handle."""

        handle: ManualTaskHandle[TaskResultT] = ManualTaskHandle(request)
        self.requests.append(cast(TaskRequest[object], request))
        self.handles.append(cast(ManualTaskHandle[object], handle))
        self.cancellations.append(cancellation)
        return handle

    def close(self) -> None:
        """Record route closure."""

        self.closed = True


class _QueuedExecutionRuntime:
    """Expose the submitter factory shape used by production runtime."""

    def __init__(self, submitter: _QueuedRuntimeSubmitter) -> None:
        """Store the submitter returned to action code."""

        self.submitter_instance = submitter
        self.calls: list[tuple[str, str, object]] = []

    def submitter(
        self,
        name: str,
        *,
        owner_id: str,
        dispatcher: object,
    ) -> _QueuedRuntimeSubmitter:
        """Record runtime route creation."""

        self.calls.append((name, owner_id, dispatcher))
        return self.submitter_instance


def _noop_output_registrar() -> object:
    """Return an Output registrar double for tests that do not restore outputs."""

    return SimpleNamespace(add_output_image=lambda *_args: None)


def _recipe_output_registrar(
    added_outputs: list[tuple[str, object, object]],
) -> object:
    """Return an Output registrar double for recipe-output tests."""

    return SimpleNamespace(
        add_output_image=lambda workflow_id, image, image_meta: added_outputs.append(
            (workflow_id, image, image_meta)
        )
    )


def test_workspace_file_actions_do_not_register_output_images_directly() -> None:
    """File actions must delegate Output materialization to the registrar port."""

    source = Path("substitute/presentation/shell/workspace_file_actions.py").read_text(
        encoding="utf-8"
    )

    assert "output_canvas_state_service" not in source
    assert ".register_output_image(" not in source


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


class _TabItem:
    """Workflow-tab item double with mutable text and route key."""

    def __init__(self, route_key: str, text: str) -> None:
        self._route_key = route_key
        self._text = text

    def routeKey(self) -> str:
        """Return the current route key."""

        return self._route_key

    def text(self) -> str:
        """Return the current tab text."""

        return self._text

    def setText(self, text: str) -> None:
        """Record tab text updates."""

        self._text = text


class _CubeStack:
    """Cube-stack double tracking placeholder tab insertion."""

    def __init__(self) -> None:
        self.items: list[object] = []
        self.cleared = 0
        self.current_indices: list[int] = []

    def count(self) -> int:
        """Return current item count."""

        return len(self.items)

    def clear(self) -> None:
        """Record clear operations."""

        self.cleared += 1
        self.items.clear()

    def insertTab(self, index: int, **kwargs: object) -> object:
        """Insert and return a placeholder tab item."""

        item = SimpleNamespace(index=index, kwargs=kwargs)
        self.items.insert(index, item)
        return item

    def setCurrentIndex(self, index: int) -> None:
        """Record current-index updates."""

        self.current_indices.append(index)


class _EditorPanel:
    """Editor-panel double tracking clear-layout calls."""

    def __init__(self) -> None:
        self.clear_calls = 0

    def clear_layout(self) -> None:
        """Record layout clearing."""

        self.clear_calls += 1


def test_on_load_clicked_reuses_blank_default_workflow_and_restores_output(
    tmp_path: Path,
) -> None:
    """Loading into the default blank workflow should reuse it and restore PNG output."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    add_workflow_calls: list[str] = []
    loader_calls: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    added_outputs: list[tuple[str, object, object]] = []
    loaded_image_calls: list[Path] = []
    source_path = tmp_path / "recipe.png"
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "LoaderCube"}},
                    global_overrides={"seed": 7},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=SimpleNamespace(
            apply_global_overrides=lambda: _append(
                add_workflow_calls,
                "overrides",
            )
        ),
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda path: _append_then(
                loaded_image_calls,
                path,
                "qimg",
            ),
            build_output_image_metadata=lambda **_kwargs: "meta",
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(cast(list[object], busy_calls)),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: _append(
            add_workflow_calls,
            "new-workflow",
        ),
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_recipe_output_registrar(added_outputs),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, str]:
            return str(source_path), "Recipes and Images"

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda callbacks, **kwargs: _append(
            loader_calls,
            {
                "callbacks": callbacks,
                **kwargs,
            },
        ),
        icon_provider=_IconProvider,
    )

    assert add_workflow_calls == ["overrides"]
    assert tab_item.text() == "Loaded Workflow"
    assert cube_stack.cleared == 1
    assert editor_panel.clear_calls == 1
    assert view._pending_cubes == {"CubeA": 0}
    assert loader_calls == [
        {
            "callbacks": "callbacks",
            "cube_id": "LoaderCube",
            "alias_name": "CubeA",
            "placeholder_index": 0,
            "buffer_patch": {"cube_id": "LoaderCube"},
            "reveal_after_load": False,
            "presentation_intent": loader_calls[0]["presentation_intent"],
            "on_load_finished": loader_calls[0]["on_load_finished"],
        }
    ]
    presentation_intent = cast(Any, loader_calls[0]["presentation_intent"])
    assert presentation_intent.select_after_load is False
    assert presentation_intent.scroll_after_load is False
    assert busy_calls == [("begin", (workflow_id, "Loading"))]
    finish_load = cast(
        Callable[[str | None], None], loader_calls[0]["on_load_finished"]
    )
    finish_load("CubeA")
    assert busy_calls == [
        ("begin", (workflow_id, "Loading")),
        ("end", "busy-token"),
    ]
    assert loaded_image_calls == [source_path]
    assert added_outputs == [(workflow_id, "qimg", "meta")]


def test_load_recipe_document_restores_discovered_png_output_siblings(
    tmp_path: Path,
) -> None:
    """Loading a recipe PNG should restore discovered same-folder output siblings."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "881_untitled_recipe_text_to_image.png"
    sibling_path = tmp_path / "881_untitled_recipe_diffusion_upscale.png"
    metadata_calls: list[dict[str, object]] = []
    added_outputs: list[tuple[str, object, object]] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }
    discovery_result = mod.RecipeOutputSiblingDiscoveryResult(
        siblings=(
            mod.RecipeOutputSibling(
                path=source_path,
                source_key="text_to_image",
                source_label="Text to Image",
                sequence=1,
                node_title="Text",
            ),
            mod.RecipeOutputSibling(
                path=sibling_path,
                source_key="diffusion_upscale",
                source_label="Diffusion Upscale",
                sequence=2,
                node_title="Upscale",
            ),
        ),
        strategy="same_folder_pattern",
    )
    discovery_calls: list[tuple[Path, str]] = []

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "LoaderCube"}},
                    global_overrides={},
                    project_name="Untitled Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda path: f"image:{path.name}",
            build_output_image_metadata=lambda **kwargs: _append_then(
                metadata_calls,
                kwargs,
                f"meta:{kwargs['source_key']}",
            ),
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_recipe_output_registrar(added_outputs),
        recipe_output_sibling_discovery_service=SimpleNamespace(
            discover_for_recipe_png=lambda path, *, workflow_name: _append_then(
                discovery_calls,
                (path, workflow_name),
                discovery_result,
            )
        ),
    )

    actions.load_recipe_document(
        source_path,
        projects_dir=tmp_path,
        cube_loader=lambda *_args, **_kwargs: None,
    )

    assert discovery_calls == [(source_path, "Untitled Workflow")]
    assert [call["file_path"] for call in metadata_calls] == [source_path, sibling_path]
    assert [call["workflow_name"] for call in metadata_calls] == [
        "Untitled Workflow",
        "Untitled Workflow",
    ]
    assert [call["source_key"] for call in metadata_calls] == [
        "text_to_image",
        "diffusion_upscale",
    ]
    assert added_outputs == [
        (
            workflow_id,
            "image:881_untitled_recipe_text_to_image.png",
            "meta:text_to_image",
        ),
        (
            workflow_id,
            "image:881_untitled_recipe_diffusion_upscale.png",
            "meta:diffusion_upscale",
        ),
    ]


def test_load_recipe_document_skips_unreadable_discovered_png_sibling(
    tmp_path: Path,
) -> None:
    """Unreadable sibling images should not block the recipe load."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    source_path = tmp_path / "881_untitled_recipe_text_to_image.png"
    broken_path = tmp_path / "881_untitled_recipe_broken.png"
    added_outputs: list[tuple[str, object, object]] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }
    discovery_result = mod.RecipeOutputSiblingDiscoveryResult(
        siblings=(
            mod.RecipeOutputSibling(
                path=source_path,
                source_key="text_to_image",
                source_label="Text to Image",
                sequence=1,
            ),
            mod.RecipeOutputSibling(
                path=broken_path,
                source_key="broken",
                source_label="Broken",
                sequence=2,
            ),
        ),
        strategy="same_folder_pattern",
    )

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={},
                    global_overrides={},
                    project_name="Untitled Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: _CubeStack()},
        editor_panels={workflow_id: _EditorPanel()},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda path: (
                None if path == broken_path else f"image:{path.name}"
            ),
            build_output_image_metadata=lambda **kwargs: f"meta:{kwargs['source_key']}",
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_recipe_output_registrar(added_outputs),
        recipe_output_sibling_discovery_service=SimpleNamespace(
            discover_for_recipe_png=lambda *_args, **_kwargs: discovery_result
        ),
    )

    result = actions.load_recipe_document(
        source_path,
        projects_dir=tmp_path,
        cube_loader=lambda *_args, **_kwargs: None,
    )

    assert result == workflow_id
    assert added_outputs == [
        (
            workflow_id,
            "image:881_untitled_recipe_text_to_image.png",
            "meta:text_to_image",
        )
    ]


def test_load_recipe_document_does_not_discover_siblings_for_text_recipe(
    tmp_path: Path,
) -> None:
    """Text recipe loads should not invoke PNG output sibling discovery."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    source_path = tmp_path / "recipe.sugar"
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    def _unexpected_discovery(*_args: object, **_kwargs: object) -> object:
        """Fail if text recipes attempt PNG sibling discovery."""

        raise AssertionError("text recipe should not discover image siblings")

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="sugar",
                ),
                parsed_script=SimpleNamespace(
                    buffers={},
                    global_overrides={},
                    project_name="Untitled Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: _CubeStack()},
        editor_panels={workflow_id: _EditorPanel()},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
        recipe_output_sibling_discovery_service=SimpleNamespace(
            discover_for_recipe_png=_unexpected_discovery
        ),
    )

    assert (
        actions.load_recipe_document(
            source_path,
            projects_dir=tmp_path,
            cube_loader=lambda *_args, **_kwargs: None,
        )
        == workflow_id
    )


def test_on_load_clicked_batches_recipe_cube_reveal_until_all_loads_finish(
    tmp_path: Path,
) -> None:
    """Recipe loads should suppress per-cube reveal and activate once at batch end."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "recipe.sugar"
    loader_calls: list[dict[str, object]] = []
    busy_calls: list[tuple[str, object]] = []
    activated: list[tuple[str, str]] = []
    callbacks = SimpleNamespace(
        activate_loaded_cube=lambda workflow_id, alias: _append(
            activated,
            (workflow_id, alias),
        )
    )
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="sugar",
                ),
                parsed_script=SimpleNamespace(
                    buffers={
                        "CubeA": {"cube_id": "LoaderCubeA"},
                        "CubeB": {"cube_id": "LoaderCubeB"},
                    },
                    global_overrides={},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(cast(list[object], busy_calls)),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: callbacks,
        output_image_registrar=_noop_output_registrar(),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, str]:
            return str(source_path), "Recipes and Images"

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda callbacks, **kwargs: _append(
            loader_calls,
            {"callbacks": callbacks, **kwargs},
        ),
        icon_provider=_IconProvider,
    )

    assert [call["reveal_after_load"] for call in loader_calls] == [False, False]
    assert activated == []

    first_finished = cast(
        Callable[[str | None], None], loader_calls[0]["on_load_finished"]
    )
    second_finished = cast(
        Callable[[str | None], None],
        loader_calls[1]["on_load_finished"],
    )
    assert callable(first_finished)
    assert callable(second_finished)
    first_finished("CubeA")
    assert activated == []
    assert busy_calls == [("begin", (workflow_id, "Loading"))]
    second_finished("CubeB")

    assert activated == [(workflow_id, "CubeB")]
    assert busy_calls == [
        ("begin", (workflow_id, "Loading")),
        ("end", "busy-token"),
    ]


def test_on_load_clicked_logs_recipe_cube_library_drift_without_dialog(
    tmp_path: Path,
) -> None:
    """Recipe loads should present Cube Library drift through the error modal system."""

    mod = _import_module()
    workflow_id = "wf-1"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "recipe.sugar"
    warning_calls: list[tuple[object, str, str]] = []
    presented_reports: list[Any] = []
    drift_buffers: list[object] = []
    loader_calls: list[dict[str, object]] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="sugar",
                ),
                parsed_script=SimpleNamespace(
                    buffers={
                        "CubeA": {
                            "cube_id": "Owner/Repo/cube-a.cube",
                        }
                    },
                    global_overrides={},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_library_management_service=SimpleNamespace(
            recipe_drift_messages=lambda buffers: _append_then(
                drift_buffers,
                buffers,
                ("Cube 'CubeA' changed.",),
            )
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(
            activate_loaded_cube=lambda *_args: None
        ),
        output_image_registrar=_noop_output_registrar(),
        error_presenter=SimpleNamespace(
            show_error_report=lambda report: _append(presented_reports, report)
        ),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, str]:
            return str(source_path), "Recipes and Images"

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    message_box = SimpleNamespace(
        critical=lambda *_args, **_kwargs: None,
        warning=lambda *args: _append(
            warning_calls,
            cast(tuple[object, str, str], args),
        ),
    )

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda callbacks, **kwargs: loader_calls.append(
            {"callbacks": callbacks, **kwargs}
        ),
        icon_provider=_IconProvider,
        message_box=message_box,
    )

    assert drift_buffers == [
        {
            "CubeA": {
                "cube_id": "Owner/Repo/cube-a.cube",
            }
        }
    ]
    assert warning_calls == []
    assert len(presented_reports) == 1
    assert presented_reports[0].kind.value == "cube_library_drift"
    assert presented_reports[0].severity.value == "warning"
    assert presented_reports[0].title == "Cube Library Notice"
    assert presented_reports[0].message == (
        "The recipe loaded with Cube Library warnings."
    )
    assert presented_reports[0].operation_context.operation == (
        "load_recipe_cube_library_drift"
    )
    assert presented_reports[0].operation_context.path == str(source_path)
    assert loader_calls[0]["cube_id"] == "Owner/Repo/cube-a.cube"


def test_on_load_clicked_uses_error_presenter_fallback_for_cube_library_drift(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Cube Library drift should still use the error modal system without injection."""

    mod = _import_module()
    workflow_id = "wf-1"
    source_path = tmp_path / "recipe.sugar"
    tab_item = _TabItem(workflow_id, "Untitled Workflow")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    presented_reports: list[Any] = []
    workflows = {
        workflow_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        )
    }

    class _Presenter:
        def __init__(self, *, parent: object | None = None) -> None:
            self.parent = parent

        def show_error_report(self, report: object) -> None:
            """Record fallback modal presentation."""

            _append(presented_reports, report)

    monkeypatch.setattr(mod, "ErrorPresenter", _Presenter)
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab_item,
            itemMap={workflow_id: tab_item},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=workflow_id,
            workflows=workflows,
            get_workflow=lambda current_id: workflows.get(current_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="sugar",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "Owner/Repo/cube-a.cube"}},
                    global_overrides={},
                    project_name="Loaded Workflow",
                ),
            )
        ),
        cube_library_management_service=SimpleNamespace(
            recipe_drift_messages=lambda _buffers: ("Cube 'CubeA' changed.",)
        ),
        cube_stacks={workflow_id: cube_stack},
        editor_panels={workflow_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(
            activate_loaded_cube=lambda *_args: None
        ),
        output_image_registrar=_noop_output_registrar(),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, str]:
            return str(source_path), "Recipes and Images"

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda *_args, **_kwargs: None,
        icon_provider=_IconProvider,
    )

    assert len(presented_reports) == 1
    assert presented_reports[0].kind.value == "cube_library_drift"
    assert presented_reports[0].severity.value == "warning"


def test_on_load_clicked_does_not_create_workflow_when_selection_is_cancelled(
    tmp_path: Path,
) -> None:
    """Cancelling file selection should not create an empty workflow tab."""

    mod = _import_module()
    current_id = "wf-1"
    new_id = "wf-2"
    current_tab = _TabItem(current_id, "Recipe 1")
    new_tab = _TabItem(new_id, "Untitled Workflow 2")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    add_calls: list[str] = []
    sugar_scripts_dir = tmp_path / "sugarscripts"
    opened_directories: list[str] = []

    workflows = {
        current_id: SimpleNamespace(stack_order=["CubeA"], cubes={"CubeA": object()}),
        new_id: SimpleNamespace(stack_order=[], cubes={}, global_overrides={}),
    }
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: current_tab,
            itemMap={current_id: current_tab, new_id: new_tab},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=current_id,
            workflows=workflows,
            get_workflow=lambda workflow_id: workflows.get(workflow_id),
        ),
        recipe_io_service=SimpleNamespace(),
        cube_stacks={new_id: cube_stack},
        editor_panels={new_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=sugar_scripts_dir,
            cubes_dir=tmp_path / "cubes",
        ),
    )

    def _add_workflow() -> None:
        add_calls.append("added")
        view.workflow_session_service.active_workflow_id = new_id

    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=_add_workflow,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            _parent: object,
            _caption: str,
            directory: str,
            _filter: str,
            **_kwargs: object,
        ) -> tuple[str, str]:
            opened_directories.append(directory)
            return "", ""

    actions.on_load_clicked(
        projects_dir=tmp_path,
        sugar_scripts_dir=sugar_scripts_dir,
        file_dialog=_Dialog,
    )

    assert add_calls == []
    assert opened_directories == [str(sugar_scripts_dir)]


def test_on_load_clicked_migrates_legacy_default_project_name_for_new_tab(
    tmp_path: Path,
) -> None:
    """Loaded legacy default project names should use current workflow labels."""

    mod = _import_module()
    current_id = "wf-1"
    new_id = "wf-2"
    current_tab = _TabItem(current_id, "Untitled Workflow")
    new_tab = _TabItem(new_id, "Untitled Workflow (2)")
    cube_stack = _CubeStack()
    editor_panel = _EditorPanel()
    source_path = tmp_path / "recipe.png"
    loader_calls: list[dict[str, object]] = []

    workflows = {
        current_id: SimpleNamespace(
            stack_order=["CubeA"],
            cubes={"CubeA": object()},
        ),
        new_id: SimpleNamespace(
            stack_order=[],
            cubes={},
            global_overrides={},
        ),
    }
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: current_tab,
            itemMap={current_id: current_tab, new_id: new_tab},
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=current_id,
            workflows=workflows,
            get_workflow=lambda workflow_id: workflows.get(workflow_id),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: SimpleNamespace(
                loaded_document=SimpleNamespace(
                    source_path=source_path,
                    source_kind="png",
                ),
                parsed_script=SimpleNamespace(
                    buffers={"CubeA": {"cube_id": "LoaderCube"}},
                    global_overrides={},
                    project_name="Untitled Recipe",
                ),
            )
        ),
        cube_stacks={new_id: cube_stack},
        editor_panels={new_id: editor_panel},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(
            load_recipe_preview_image=lambda _path: None,
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
        editor_busy=_EditorBusyRecorder(),
    )

    def _add_workflow() -> None:
        view.workflow_session_service.active_workflow_id = new_id

    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=_add_workflow,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=_noop_output_registrar(),
    )

    class _Dialog:
        @staticmethod
        def getOpenFileName(
            *_args: object,
            **_kwargs: object,
        ) -> tuple[str, str]:
            return str(source_path), "Recipes and Images"

    class _IconProvider:
        class CLOSE:
            @staticmethod
            def icon() -> str:
                return "close-icon"

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=_Dialog,
        cube_loader=lambda callbacks, **kwargs: _append(
            loader_calls,
            {"callbacks": callbacks, **kwargs},
        ),
        icon_provider=_IconProvider,
    )

    assert new_tab.text() == "Untitled Workflow (2)"
    assert loader_calls[0]["cube_id"] == "LoaderCube"


def test_on_save_clicked_uses_recipe_service_default_path_policy(
    tmp_path: Path,
) -> None:
    """Save should delegate canonical path selection to the recipe I/O service."""

    mod = _import_module()
    save_calls: list[tuple[str, object, Path]] = []
    built_paths: list[tuple[str, Path]] = []
    sugar_scripts_dir = tmp_path / "sugarscripts"
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: _TabItem("wf-1", "Recipe"),
        ),
        recipe_io_service=SimpleNamespace(
            build_default_recipe_path=lambda workflow_name, sugar_root: _append_then(
                built_paths,
                (workflow_name, sugar_root),
                (sugar_root / workflow_name / f"{workflow_name}.sugar").resolve(),
            ),
            save_workflow_recipe_to_default_path=lambda workflow_name, workflow, sugar_scripts_dir: (
                _append_then(
                    save_calls,
                    (workflow_name, workflow, sugar_scripts_dir),
                    (
                        sugar_scripts_dir / workflow_name / f"{workflow_name}.sugar"
                    ).resolve(),
                )
            ),
        ),
        get_active_workflow=lambda: {"nodes": {}},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=sugar_scripts_dir,
            cubes_dir=tmp_path / "cubes",
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
    )

    actions.on_save_clicked(sugar_scripts_dir=sugar_scripts_dir)

    assert built_paths == [("Recipe", sugar_scripts_dir)]
    assert save_calls == [("Recipe", {"nodes": {}}, sugar_scripts_dir)]


def test_on_save_as_clicked_validates_destination_via_recipe_service(
    tmp_path: Path,
) -> None:
    """Save As should use the recipe service for default-path and destination validation."""

    mod = _import_module()
    validated_paths: list[Path] = []
    saved_paths: list[tuple[Path, str, object]] = []
    sugar_scripts_dir = tmp_path / "sugarscripts"
    destination = sugar_scripts_dir / "custom.sugar"
    file_dialog = SimpleNamespace(
        getSaveFileName=lambda *_args, **_kwargs: (str(destination), "Sugar Script")
    )
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: _TabItem("wf-1", "Recipe"),
        ),
        recipe_io_service=SimpleNamespace(
            build_default_recipe_path=lambda workflow_name, sugar_root: (
                sugar_root / workflow_name / f"{workflow_name}.sugar"
            ).resolve(),
            validate_recipe_destination=lambda path: _append_then(
                validated_paths,
                path,
                path,
            ),
            save_workflow_recipe=lambda path, *, workflow_name, workflow: _append(
                saved_paths, (path, workflow_name, workflow)
            ),
        ),
        get_active_workflow=lambda: {"nodes": {}},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=sugar_scripts_dir,
            cubes_dir=tmp_path / "cubes",
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
    )

    actions.on_save_as_clicked(
        sugar_scripts_dir=sugar_scripts_dir, file_dialog=file_dialog
    )

    assert validated_paths == [destination.resolve()]
    assert saved_paths == [(destination.resolve(), "Recipe", {"nodes": {}})]


def test_on_export_clicked_validates_destination_via_export_service(
    tmp_path: Path,
) -> None:
    """Export should delegate default-path and destination validation to the export service."""

    mod = _import_module()
    destination = tmp_path / "Recipe.json"
    validated_paths: list[Path] = []
    export_calls: list[dict[str, object]] = []
    file_dialog = SimpleNamespace(
        getSaveFileName=lambda *_args, **_kwargs: (str(destination), "ComfyUI Workflow")
    )
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: _TabItem("wf-1", "Recipe"),
        ),
        recipe_io_service=SimpleNamespace(
            serialize_workflow_to_sugar_script=lambda workflow: "# sugar"
        ),
        workflow_export_service=SimpleNamespace(
            build_default_export_path=lambda workflow_name, output_dir: (
                output_dir / f"{workflow_name}.json"
            ).resolve(),
            validate_export_destination=lambda path: _append_then(
                validated_paths,
                path,
                path,
            ),
            export_workflow_json=lambda **kwargs: _append(export_calls, kwargs),
        ),
        get_active_workflow=lambda: {"nodes": {}},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path / "cubes",
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
    )

    actions.on_export_comfy_workflow_clicked(
        output_dir=tmp_path,
        file_dialog=file_dialog,
        message_box=SimpleNamespace(critical=lambda *_args, **_kwargs: None),
    )

    assert validated_paths == [destination.resolve()]
    assert export_calls == [
        {
            "destination_path": destination.resolve(),
            "sugar_script_text": "# sugar",
            "output_dir": tmp_path,
            "workflow": {"nodes": {}},
        }
    ]


def test_on_export_clicked_reports_failure_through_error_presenter(
    tmp_path: Path,
) -> None:
    """Export failures should use the unified error modal presenter when available."""

    mod = _import_module()
    destination = tmp_path / "Recipe.json"
    presented: list[dict[str, Any]] = []
    critical_calls: list[object] = []
    failure = RuntimeError("cannot export")
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: _TabItem("wf-1", "Recipe"),
        ),
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        recipe_io_service=SimpleNamespace(
            serialize_workflow_to_sugar_script=lambda workflow: "# sugar"
        ),
        workflow_export_service=SimpleNamespace(
            build_default_export_path=lambda workflow_name, output_dir: (
                output_dir / f"{workflow_name}.json"
            ).resolve(),
            validate_export_destination=lambda path: path,
            export_workflow_json=lambda **_kwargs: (_ for _ in ()).throw(failure),
        ),
        get_active_workflow=lambda: {"nodes": {}},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path, sugar_scripts_dir=tmp_path / "sugarscripts"
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: _append(presented, kwargs)
        ),
    )

    actions.on_export_comfy_workflow_clicked(
        output_dir=tmp_path,
        file_dialog=SimpleNamespace(
            getSaveFileName=lambda *_args, **_kwargs: (
                str(destination),
                "ComfyUI Workflow",
            )
        ),
        message_box=SimpleNamespace(
            critical=lambda *args, **_kwargs: _append(critical_calls, args)
        ),
    )

    assert critical_calls == []
    assert presented[0]["title"] == "Export workflow failed"
    assert presented[0]["stage"] == "export"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "export_workflow_json"
    assert context.workflow_id == "wf-1"
    assert context.workflow_name == "Recipe"
    assert context.path == str(destination.resolve())


def test_on_load_clicked_reports_failure_through_error_presenter(
    tmp_path: Path,
) -> None:
    """Recipe load failures should use the unified error modal presenter."""

    mod = _import_module()
    source_path = tmp_path / "broken.sugar"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("bad")
    presented: list[dict[str, Any]] = []
    critical_calls: list[object] = []
    failure = ValueError("bad recipe")
    current_id = "wf-1"
    tab = _TabItem(current_id, "Untitled Workflow")
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            currentIndex=lambda: 0,
            tabItem=lambda _index: tab,
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id=current_id,
            workflows={
                current_id: SimpleNamespace(
                    stack_order=[],
                    cubes={},
                    global_overrides={},
                )
            },
            get_workflow=lambda workflow_id: (
                SimpleNamespace(
                    stack_order=[],
                    cubes={},
                    global_overrides={},
                )
                if workflow_id == current_id
                else None
            ),
        ),
        recipe_io_service=SimpleNamespace(
            load_and_parse_recipe_document=lambda _path: (_ for _ in ()).throw(failure)
        ),
        cube_stacks={},
        editor_panels={},
        active_override_manager=None,
        canvas_io_service=SimpleNamespace(),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path, sugar_scripts_dir=tmp_path / "sugarscripts"
        ),
    )
    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=lambda: None,
        build_cube_load_ui_callbacks=lambda **_kwargs: "callbacks",
        output_image_registrar=_noop_output_registrar(),
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: _append(presented, kwargs)
        ),
    )

    actions.on_load_clicked(
        projects_dir=tmp_path,
        file_dialog=SimpleNamespace(
            getOpenFileName=lambda *_args, **_kwargs: (
                str(source_path),
                "Recipes and Images",
            )
        ),
        message_box=SimpleNamespace(
            critical=lambda *args, **_kwargs: _append(critical_calls, args)
        ),
    )

    assert critical_calls == []
    assert presented[0]["title"] == "Load recipe failed"
    assert presented[0]["stage"] == "load"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "load_recipe"
    assert context.workflow_id == current_id
    assert context.path == str(source_path.resolve())


def test_open_sugar_snapshot_as_new_workflow_materializes_unique_tab(
    tmp_path: Path,
) -> None:
    """Snapshot open should create a new workflow and materialize parsed buffers."""

    mod = _import_module()
    inserted: list[dict[str, object]] = []
    loaded: list[dict[str, object]] = []
    calls: list[str] = []

    class _CubeStack:
        """Minimal cube stack for snapshot materialization."""

        def __init__(self) -> None:
            """Initialize tab item collection."""

            self.items: list[object] = []

        def clear(self) -> None:
            """Record clear."""

            calls.append("clear-stack")

        def count(self) -> int:
            """Return current item count."""

            return len(self.items)

        def insertTab(self, index: int, **kwargs: object) -> object:
            """Insert and return placeholder item."""

            item = object()
            self.items.insert(index, item)
            inserted.append(kwargs)
            return item

        def setCurrentIndex(self, index: int) -> None:
            """Record current index."""

            calls.append(f"current:{index}")

    class _EditorPanel:
        """Minimal editor panel for snapshot materialization."""

        def clear_layout(self) -> None:
            """Record layout clear."""

            calls.append("clear-editor")

    class _Icon:
        """Placeholder icon provider token."""

        def icon(self) -> object:
            """Return icon payload."""

            return "icon"

    active_id = {"value": "wf-a"}
    tab_items = {
        "wf-existing": _TabItem("wf-existing", "Recipe"),
        "wf-a": _TabItem("wf-a", "Untitled Workflow"),
    }
    view = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(itemMap=tab_items),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={
                "wf-a": SimpleNamespace(global_overrides={}),
            },
        ),
        recipe_io_service=SimpleNamespace(
            parse_recipe_script=lambda _text: SimpleNamespace(
                buffers={
                    "A": {
                        "cube_id": "cube-a",
                    }
                },
                global_overrides={"seed": 1},
                project_name=None,
            )
        ),
        cube_stacks={"wf-a": _CubeStack()},
        editor_panels={"wf-a": _EditorPanel()},
        active_override_manager=SimpleNamespace(
            apply_global_overrides=lambda: _append(calls, "overrides")
        ),
        _pending_cubes={},
        path_bundle=SimpleNamespace(
            projects_dir=tmp_path,
            sugar_scripts_dir=tmp_path / "sugarscripts",
            cubes_dir=tmp_path,
        ),
        editor_busy=SimpleNamespace(
            begin=lambda workflow_id, *, message="Loading": _append_then(
                calls,
                f"busy:{workflow_id}:{message}",
                object(),
            ),
            end=lambda _token: _append(calls, "busy:end"),
            set_cancel_callback=lambda _token, _callback: None,
            update_download=lambda _token, _state: None,
        ),
    )

    def _add_workflow() -> None:
        """Activate the prepared workflow double."""

        view.workflow_session_service.active_workflow_id = active_id["value"]

    def _cube_loader(callbacks: object, **kwargs: object) -> None:
        """Record cube load request and finish synchronously."""

        del callbacks
        loaded.append(kwargs)
        on_load_finished = kwargs.get("on_load_finished")
        if callable(on_load_finished):
            on_load_finished("A")

    actions = mod.WorkspaceFileActions(
        view,
        add_workflow_tab_requested=_add_workflow,
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(
            activate_loaded_cube=lambda workflow_id, alias: _append(
                calls,
                f"activate:{workflow_id}:{alias}",
            )
        ),
        output_image_registrar=_noop_output_registrar(),
    )

    opened_id = actions.open_sugar_snapshot_as_new_workflow(
        workflow_name="Recipe",
        sugar_script_text="# sugar",
        projects_dir=tmp_path,
        icon_provider=SimpleNamespace(CLOSE=_Icon()),
        cube_loader=_cube_loader,
    )

    assert opened_id == "wf-a"
    assert tab_items["wf-a"].text() == "Recipe (2)"
    assert view.workflow_session_service.workflows["wf-a"].global_overrides == {
        "seed": 1
    }
    assert inserted[0]["routeKey"] == "loading:A"
    assert loaded[0]["cube_id"] == "cube-a"
