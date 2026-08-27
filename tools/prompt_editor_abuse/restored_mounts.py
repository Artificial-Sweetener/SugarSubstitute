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

"""Mount prompt abuse fields through persisted workspace and PNG restore paths."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from PIL import Image
from PIL.PngImagePlugin import PngInfo
from PySide6.QtGui import QImage
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.application.recipes import RecipeIoService
from substitute.application.cubes import LoadedCubeDefinition
from substitute.application.workflows import DEFAULT_WORKFLOW_TAB_LABEL
from substitute.application.workspace_state import (
    InitialWorkspaceRestorePlanService,
    RestoredEditorProjectionCacheExtractor,
    RestoreProjectionArtifact,
    RestoreProjectionCacheState,
    SnapshotNormalizationService,
    restore_projection_artifact_to_json,
)
from substitute.domain.session import SESSION_SNAPSHOT_SCHEMA_VERSION, SessionSnapshot
from substitute.domain.workflow import ImageMeta, WorkflowState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot
from substitute.infrastructure.persistence.file_recipe_repository import (
    FileRecipeRepository,
)
from substitute.infrastructure.persistence.file_restore_projection_cache import (
    FileRestoreProjectionCacheRepository,
)
from substitute.infrastructure.persistence.file_session_snapshot_repository import (
    FileSessionSnapshotRepository,
)
from substitute.infrastructure.cache_lifecycle.atomic_json import (
    write_json_atomically,
)
from substitute.presentation.shell.restored_workflow_materializer import (
    RestoredWorkflowMaterializer,
)
from substitute.presentation.shell.restore_projection_controller import (
    RestoreProjectionController,
)
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)
from substitute.presentation.shell.workspace_file_actions import WorkspaceFileActions
from tests.support.prompt_editor.real_shell.models import (
    PromptFieldHandle,
    PromptWorkflowHandle,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)
from tests.support.prompt_editor.real_shell.workflows import _prompt_cube_state

from .models import PromptAbuseScenario

_WORKSPACE_SCHEMA_VERSION = "1"
_CUBE_ALIAS = "Prompt Cube"
_FIELD_KEY = (_CUBE_ALIAS, "positive_prompt", "text")
_V0_19_2_RELEASED_AT = "2026-08-03T21:54:32+00:00"


def mount_cached_workspace_prompt(
    harness: PromptEditorRealShellScenario,
    scenario: PromptAbuseScenario,
    *,
    alias: str,
) -> PromptFieldHandle:
    """Round-trip a warm workspace cache and mount its restored prompt field."""

    fixture_root = harness.artifact_root / "restore-fixtures" / alias
    workflow_snapshot = _prompt_workflow_snapshot(alias, scenario.initial_text)
    workspace = _workspace_snapshot(workflow_snapshot)
    session_repository = FileSessionSnapshotRepository(fixture_root / "session")
    cache_repository = FileRestoreProjectionCacheRepository(fixture_root / "cache")
    session_repository.save(
        SessionSnapshot(
            schema_version=SESSION_SNAPSHOT_SCHEMA_VERSION,
            captured_at=datetime.now(UTC),
            workspace=workspace,
        )
    )
    artifact = RestoredEditorProjectionCacheExtractor().capture(
        snapshot=workspace,
        target_key="prompt-abuse",
        editor_panels={},
        node_definition_gateway=harness.shell.node_definition_gateway,
    )
    if scenario.mount_source == "workspace_cache_0_19_2":
        _write_v0_19_2_stale_artifact(cache_repository.path, artifact)
    else:
        cache_repository.save(artifact)
    plan = InitialWorkspaceRestorePlanService(
        repository=session_repository,
        normalizer=SnapshotNormalizationService(),
        restore_projection_repository=cache_repository,
        restore_projection_target_key="prompt-abuse",
    ).build()
    if plan.workspace is None:
        raise RuntimeError("Prompt abuse cache fixture did not produce a restore plan.")
    if scenario.mount_source == "workspace_cache_0_19_2":
        if plan.provisional_restore_projection is not None:
            raise RuntimeError("Prompt abuse v0.19.2 cache was accepted unexpectedly.")
        validation = plan.restore_projection_validation
        if (
            validation is None
            or validation.state is not RestoreProjectionCacheState.MISSING
        ):
            raise RuntimeError("Prompt abuse v0.19.2 cache was not rejected as stale.")
        return _mount_uncached_restored_workflow(
            harness,
            plan.workspace.workflows[0],
            alias=alias,
        )
    if plan.provisional_restore_projection is None:
        raise RuntimeError("Prompt abuse warm cache was not accepted provisionally.")
    validation = plan.restore_projection_validation
    if (
        validation is None
        or validation.state is not RestoreProjectionCacheState.BACKEND_PENDING
    ):
        raise RuntimeError("Prompt abuse warm cache was not accepted provisionally.")
    restored_snapshot = plan.workspace.workflows[0]
    return _mount_restored_workflow(
        harness,
        restored_snapshot,
        artifact=plan.provisional_restore_projection,
        cache_repository=cache_repository,
        alias=alias,
    )


def _mount_uncached_restored_workflow(
    harness: PromptEditorRealShellScenario,
    snapshot: WorkflowSnapshot,
    *,
    alias: str,
) -> PromptFieldHandle:
    """Project a restored session through the production cache-miss surface path."""

    workflow_id = snapshot.workflow_id
    harness.shell.install_workflow_surface(workflow_id)
    RestoredWorkflowMaterializer(harness.shell).add_restored_workflow(
        snapshot,
        activate=True,
    )
    completed: list[bool] = []
    refresher = ActiveWorkflowSurfaceRefresher(harness.shell)
    setattr(harness.shell, "active_workflow_surface_refresher", refresher)
    refresher.refresh_active_workflow_surface(
        force_refresh=True,
        on_complete=lambda: completed.append(True),
    )
    harness.wait_until(lambda: bool(completed))
    harness.wait_for_queued_delivery()
    return _field_handle(
        harness,
        alias=alias,
        workflow_id=workflow_id,
        workflow=snapshot.workflow,
    )


def mount_image_sugar_script_prompt(
    harness: PromptEditorRealShellScenario,
    scenario: PromptAbuseScenario,
    *,
    alias: str,
) -> PromptFieldHandle:
    """Load a real PNG Sugar Script and mount the workflow it materializes."""

    fixture_root = harness.artifact_root / "restore-fixtures" / alias
    fixture_root.mkdir(parents=True, exist_ok=True)
    image_path = fixture_root / "attached-sugar-script.png"
    _write_recipe_png(image_path, scenario.initial_text)
    workflow_id = f"workflow-{alias}"
    workflow = WorkflowState(metadata={"name": alias})
    harness.shell.workflow_session_service.add_existing_workflow(
        workflow_id,
        workflow,
        activate=True,
    )
    harness.shell.workflow_tabbar.addTab(workflow_id, DEFAULT_WORKFLOW_TAB_LABEL)
    harness.shell.install_workflow_surface(workflow_id)
    panel = harness.shell.editor_panels[workflow_id]
    harness.shell.editor_panel_container.setCurrentWidget(panel)
    harness.shell.editor_panel = panel
    panel.show()
    setattr(
        harness.shell,
        "recipe_io_service",
        RecipeIoService(recipe_repository=FileRecipeRepository()),
    )
    setattr(
        harness.shell,
        "canvas_io_service",
        SimpleNamespace(
            load_recipe_preview_image=lambda path: QImage(str(path)),
            build_output_image_metadata=_loaded_image_meta,
        ),
    )
    setattr(harness.shell, "_pending_cubes", {})
    harness.shell.editor_busy = SimpleNamespace(
        begin=lambda _workflow_id, *, message="Loading": (workflow_id, message),
        end=lambda _token: None,
        set_cancel_callback=lambda _token, _callback: None,
        update_download=lambda _token, _state: None,
        refresh_active_surface=lambda *_args, **_kwargs: None,
    )

    def load_recipe_cube(_callbacks: object, **kwargs: object) -> None:
        """Materialize the deterministic cube at the external loader boundary."""

        buffer_patch = cast(dict[str, object], kwargs["buffer_patch"])
        prompt_text = _prompt_text_from_recipe_buffer(buffer_patch)
        cube_state = _prompt_cube_state(prompt_text, alias=_CUBE_ALIAS)
        workflow.cubes = {_CUBE_ALIAS: cube_state}
        workflow.stack_order = [_CUBE_ALIAS]
        panel.load_all_cubes(
            [(_CUBE_ALIAS, cube_state)],
            cube_states={_CUBE_ALIAS: cube_state},
            stack_order=[_CUBE_ALIAS],
        )
        panel.reveal_loaded_cube(_CUBE_ALIAS)
        on_load_finished = kwargs.get("on_load_finished")
        if callable(on_load_finished):
            on_load_finished(_CUBE_ALIAS)

    errors: list[object] = []
    actions = WorkspaceFileActions(
        cast(Any, harness.shell),
        add_workflow_tab_requested=lambda: _unexpected_new_workflow(alias),
        build_cube_load_ui_callbacks=lambda **_kwargs: SimpleNamespace(),
        output_image_registrar=SimpleNamespace(
            add_output_image=(
                harness.shell.workspace_canvas_actions.handle_loaded_output_image
            )
        ),
        error_presenter=SimpleNamespace(
            show_exception_report=lambda **kwargs: errors.append(kwargs)
        ),
    )
    loaded_workflow_id = actions.load_recipe_document(
        image_path,
        projects_dir=fixture_root,
        cube_loader=cast(Any, load_recipe_cube),
        icon_provider=FIF,
    )
    if loaded_workflow_id != workflow_id or errors:
        raise RuntimeError(
            "Prompt abuse PNG Sugar Script did not materialize its workflow."
        )
    harness.wait_for_queued_delivery()
    return _field_handle(
        harness,
        alias=alias,
        workflow_id=workflow_id,
        workflow=workflow,
    )


def _mount_restored_workflow(
    harness: PromptEditorRealShellScenario,
    snapshot: WorkflowSnapshot,
    *,
    artifact: RestoreProjectionArtifact,
    cache_repository: FileRestoreProjectionCacheRepository,
    alias: str,
) -> PromptFieldHandle:
    """Project one persisted workflow snapshot through the restore materializer."""

    workflow_id = snapshot.workflow_id
    harness.shell.install_workflow_surface(workflow_id)
    RestoredWorkflowMaterializer(harness.shell).add_restored_workflow(
        snapshot,
        activate=True,
    )
    completed: list[bool] = []
    setattr(
        harness.shell,
        "active_workflow_surface_refresher",
        ActiveWorkflowSurfaceRefresher(harness.shell),
    )
    setattr(harness.shell, "restore_projection_cache_repository", cache_repository)
    setattr(
        harness.shell,
        "cube_load_service",
        _RestoredPromptCubeLoader(snapshot.workflow),
    )
    setattr(harness.shell, "_prehydrated_restore_finalized", False)
    setattr(harness.shell, "_prehydrated_restore_runtime_prepared", True)
    setattr(
        harness.shell,
        "_prehydrated_active_workflow_projection_pending",
        workflow_id,
    )
    started = RestoreProjectionController(
        harness.shell
    ).start_pre_show_restore_projection(
        artifact,
        fallback_workflow_id=workflow_id,
        on_complete=lambda: completed.append(True),
    )
    if not started:
        raise RuntimeError("Prompt abuse cache did not start pre-show projection.")
    harness.wait_until(lambda: bool(completed))
    harness.wait_for_queued_delivery()
    return _field_handle(
        harness,
        alias=alias,
        workflow_id=workflow_id,
        workflow=snapshot.workflow,
    )


def _field_handle(
    harness: PromptEditorRealShellScenario,
    *,
    alias: str,
    workflow_id: str,
    workflow: WorkflowState,
) -> PromptFieldHandle:
    """Resolve the mounted production prompt editor into a harness field handle."""

    cube_state = workflow.cubes[_CUBE_ALIAS]
    harness.workflow_handles[alias] = PromptWorkflowHandle(
        alias=alias,
        workflow_id=workflow_id,
        cube_alias=_CUBE_ALIAS,
        cube_state=cube_state,
    )
    field = harness.workflows.prompt_field(alias)
    harness.observability.install(field)
    return field


def _prompt_workflow_snapshot(alias: str, source: str) -> WorkflowSnapshot:
    """Build one session-serializable prompt workflow snapshot."""

    workflow_id = f"workflow-{alias}"
    cube_state = _prompt_cube_state(source, alias=_CUBE_ALIAS)
    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label=alias,
        workflow=WorkflowState(
            cubes={_CUBE_ALIAS: cube_state},
            stack_order=[_CUBE_ALIAS],
            metadata={"name": alias},
        ),
        active_cube_alias=_CUBE_ALIAS,
    )


def _workspace_snapshot(workflow: WorkflowSnapshot) -> WorkspaceSnapshot:
    """Wrap one prompt workflow in the persisted startup workspace shape."""

    return WorkspaceSnapshot(
        schema_version=_WORKSPACE_SCHEMA_VERSION,
        workflows=(workflow,),
        tab_order=(workflow.workflow_id,),
        active_route=workflow.workflow_id,
        active_workflow_id=workflow.workflow_id,
    )


def _write_recipe_png(path: Path, source: str) -> None:
    """Write a PNG carrying the production Sugar Script metadata key."""

    script = (
        f'use "PromptHarness.cube" as "{_CUBE_ALIAS}"\n'
        f'set "{_CUBE_ALIAS}".positive_prompt.text = '
        f"{json.dumps(source, ensure_ascii=False)}\n"
    )
    metadata = PngInfo()
    metadata.add_text("sugar_script", script)
    Image.new("RGB", (8, 8), color=(30, 30, 30)).save(
        path,
        pnginfo=metadata,
    )


def _prompt_text_from_recipe_buffer(buffer: dict[str, object]) -> str:
    """Read the parsed prompt value at the deterministic recipe fixture path."""

    nodes = cast(dict[str, object], buffer["nodes"])
    prompt = cast(dict[str, object], nodes["positive_prompt"])
    inputs = cast(dict[str, object], prompt["inputs"])
    return str(inputs["text"])


class _RestoredPromptCubeLoader:
    """Return the persisted prompt cube as the live backend definition."""

    def __init__(self, workflow: WorkflowState) -> None:
        """Store the workflow whose cube identity must validate."""

        self._workflow = workflow

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return the exact definition referenced by the restored artifact."""

        del cube_load_trace_id
        cube = self._workflow.cubes[_CUBE_ALIAS]
        if (cube_id, version) != (cube.cube_id, cube.version):
            raise ValueError("Prompt abuse cache requested an unexpected cube.")
        return LoadedCubeDefinition(
            cube_id=cube.cube_id,
            version=cube.version,
            display_name=cube.display_name,
            graph=cube.original_cube,
            ui_payload=cube.ui or {},
        )


def _write_v0_19_2_stale_artifact(
    path: Path,
    artifact: RestoreProjectionArtifact,
) -> None:
    """Write the exact released schema-2 envelope with stale prompt metadata."""

    workflow = artifact.workflows[0]
    cube_stack = workflow.cube_stack
    if cube_stack is None or not cube_stack.cubes:
        raise RuntimeError("Prompt abuse legacy cache requires one cube projection.")
    cube = cube_stack.cubes[0]
    section = replace(
        cube.section,
        resolved_field_specs={
            "positive_prompt": {
                "text": {
                    "presentation": "prompt_box",
                    "field_type": "STRING",
                    "style": {"cache_release": "0.19.2"},
                }
            }
        },
        prompt_field_metadata={
            "positive_prompt": {
                "text": {
                    "field_type": "STRING",
                    "style": {"cache_release": "0.19.2"},
                }
            }
        },
    )
    legacy_cube = replace(cube, section=section)
    legacy_stack = replace(cube_stack, cubes=(legacy_cube,))
    legacy_workflow = replace(workflow, cube_stack=legacy_stack)
    stale_artifact = replace(
        artifact,
        created_at=_V0_19_2_RELEASED_AT,
        workflows=(legacy_workflow,),
    )
    payload = restore_projection_artifact_to_json(stale_artifact)
    payload["schema_version"] = 2
    payload["app_projection_version"] = 3
    payload["prompt_editor_feature_profile_fingerprint"] = "v0.19.2-stale-profile"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomically(path, payload)


def _loaded_image_meta(**values: object) -> ImageMeta:
    """Build the domain metadata consumed by production output registration."""

    return ImageMeta(
        workflow_name=str(values["workflow_name"]),
        cube_name=str(values["source_label"] or values["node_meta_title"]),
        image_number=1,
        suffix="",
        path=str(values["file_path"]),
        source_key=str(values.get("source_key", "")),
        source_label=str(values.get("source_label", "")),
        scene_run_id=str(values.get("scene_run_id") or ""),
        scene_key=str(values.get("scene_key") or ""),
        scene_title=str(values.get("scene_title") or ""),
        scene_order=cast(int | None, values.get("scene_order")),
        scene_count=cast(int | None, values.get("scene_count")),
        width=cast(int | None, values.get("width")),
        height=cast(int | None, values.get("height")),
    )


def _unexpected_new_workflow(alias: str) -> None:
    """Fail when the blank recipe target unexpectedly creates another tab."""

    raise RuntimeError(f"Recipe mount {alias!r} unexpectedly requested a new workflow.")


__all__ = [
    "mount_cached_workspace_prompt",
    "mount_image_sugar_script_prompt",
]
