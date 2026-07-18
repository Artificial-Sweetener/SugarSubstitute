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

"""Exercise the real mixed-document session and projection-cache restore lifecycle."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from substitute.application.cubes import LoadedCubeDefinition, LoadedCubeRuntime
from substitute.application.node_behavior import NodeBehaviorRuntimeState
from substitute.application.workspace_state import (
    InitialWorkspaceRestorePlan,
    InitialWorkspaceRestorePlanService,
    RestoredEditorProjectionCacheExtractor,
    SessionAutosaveService,
    SnapshotCaptureService,
    SnapshotNormalizationService,
    WorkspaceMaterializationService,
    WorkspaceRuntimeHydrationService,
)
from substitute.application.workspace_state.restore_projection_backend_identity import (
    RestoreProjectionBackendIdentityService,
)
from substitute.application.workspace_state.restore_projection_validation import (
    RestoreProjectionValidationResult,
    RestoreProjectionValidationService,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import CubeState, WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.infrastructure.persistence.file_restore_projection_cache import (
    FileRestoreProjectionCacheRepository,
)
from substitute.infrastructure.persistence.file_session_snapshot_repository import (
    FileSessionSnapshotRepository,
)


class HeadlessWorkspaceRestoreHarness:
    """Drive forced save, cold restore, warm cache restore, and materialization."""

    def __init__(self, root: Path) -> None:
        """Create isolated real file repositories and deterministic collaborators."""

        self.capture_port = MixedWorkflowCapturePort()
        self.session_repository = FileSessionSnapshotRepository(root / "session")
        self.cache_repository = FileRestoreProjectionCacheRepository(root / "cache")
        self.cube_loader = HarnessCubeLoader()
        self.node_gateway = HarnessNodeDefinitionGateway()

    def force_save(self) -> bool:
        """Persist the live mixed workspace through production capture and autosave."""

        return SessionAutosaveService(
            capture_service=SnapshotCaptureService(),
            repository=self.session_repository,
        ).force_save(self.capture_port)

    def build_restore_plan(self) -> InitialWorkspaceRestorePlan:
        """Load, normalize, and prevalidate the persisted session and cache."""

        return InitialWorkspaceRestorePlanService(
            repository=self.session_repository,
            normalizer=SnapshotNormalizationService(),
            restore_projection_repository=self.cache_repository,
            restore_projection_target_key="managed-comfy",
        ).build()

    def hydrate(self, snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot:
        """Hydrate cube runtime state while preserving direct authoring state."""

        return (
            WorkspaceRuntimeHydrationService(
                cube_load_service=self.cube_loader,
                node_behavior_service=HarnessNodeBehaviorService(),
            )
            .hydrate(snapshot)
            .snapshot
        )

    def materialize(self, snapshot: WorkspaceSnapshot) -> HarnessMaterializationPort:
        """Materialize the workspace through the production application service."""

        port = HarnessMaterializationPort()
        WorkspaceMaterializationService().materialize(snapshot, port)
        return port

    def capture_projection_cache(self, snapshot: WorkspaceSnapshot) -> None:
        """Persist a live validated projection artifact for the next warm restore."""

        RestoredEditorProjectionCacheExtractor().capture_and_store(
            repository=self.cache_repository,
            snapshot=snapshot,
            target_key="managed-comfy",
            editor_panels={},
            node_definition_gateway=self.node_gateway,
        )

    def validate_after_backend(
        self,
        plan: InitialWorkspaceRestorePlan,
    ) -> RestoreProjectionValidationResult:
        """Validate a provisional artifact against deterministic live definitions."""

        artifact = plan.provisional_restore_projection
        if artifact is None:
            raise AssertionError("Expected a provisional restore projection artifact.")
        identity = RestoreProjectionBackendIdentityService().collect(
            artifact,
            cube_loader=self.cube_loader,
            node_definition_gateway=self.node_gateway,
        )
        return RestoreProjectionValidationService().validate_after_backend(
            artifact,
            live_cube_fingerprints=identity.cube_fingerprints,
            live_node_fingerprints=identity.node_fingerprints,
        )


class MixedWorkflowCapturePort:
    """Expose one cube tab and one direct Comfy tab to snapshot capture."""

    def __init__(self) -> None:
        """Build render-relevant state for both document kinds."""

        cube = CubeState(
            cube_id="cube.scene",
            version="1.0.0",
            alias="Scene",
            original_cube=HarnessCubeLoader.definition.graph,
            buffer=deepcopy(HarnessCubeLoader.definition.graph),
            display_name="Scene",
            ui=deepcopy(HarnessCubeLoader.definition.ui_payload),
        )
        self.workflows = {
            "cube": WorkflowState(cubes={"Scene": cube}, stack_order=["Scene"]),
            "direct": WorkflowState(
                direct_workflow=DirectWorkflowState(
                    source_path=Path("workflows/direct.json"),
                    source_workflow={"nodes": {}},
                    buffer={
                        "nodes": {
                            "10": {
                                "class_type": "KSampler",
                                "inputs": {"seed": 17},
                                "mode": 4,
                            }
                        }
                    },
                    ui={"expanded": {"10": False}},
                    dirty=True,
                ),
                global_overrides={"seed": {"value": 23}},
            ),
        }
        self.workflows["direct"].canvas.active_canvas_route = "output:scene-2"

    def workflow_ids_in_order(self) -> tuple[str, ...]:
        """Return mixed tab order."""

        return ("cube", "direct")

    def active_workspace_route(self) -> str:
        """Return the direct workflow as the visible route."""

        return "direct"

    def active_workflow_id(self) -> str:
        """Return the direct workflow as the active tab."""

        return "direct"

    def workflow_state(self, workflow_id: str) -> WorkflowState | None:
        """Return live workflow state by tab id."""

        return self.workflows.get(workflow_id)

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return deterministic tab labels."""

        return {"cube": "Cube", "direct": "Direct"}[workflow_id]

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return cube focus only for the cube-stack document."""

        return "Scene" if workflow_id == "cube" else None

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return no input images."""

        _ = workflow_id, workflow
        return ()

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return no input masks."""

        _ = workflow_id, workflow
        return ()

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return no output images."""

        _ = workflow_id, workflow
        return ()

    def editor_viewport_snapshot(
        self, workflow_id: str
    ) -> EditorViewportSnapshot | None:
        """Return document-appropriate editor scroll state."""

        if workflow_id == "direct":
            return EditorViewportSnapshot(
                scroll_value=73,
                scroll_maximum=200,
                anchor_cube_alias=None,
            )
        return EditorViewportSnapshot(
            scroll_value=12,
            scroll_maximum=100,
            anchor_cube_alias="Scene",
        )

    def shell_layout_snapshot(self) -> ShellLayoutSnapshot | None:
        """Return a deterministic shell layout."""

        return ShellLayoutSnapshot(editor_panel_width=520, canvas_panel_width=640)


class HarnessCubeLoader:
    """Load one real-shaped deterministic cube definition and runtime."""

    definition = LoadedCubeDefinition(
        cube_id="cube.scene",
        version="1.0.0",
        display_name="Scene",
        graph={
            "nodes": {
                "1": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "cube prompt"},
                }
            }
        },
        ui_payload={
            "canonical_cube": {"cube_id": "cube.scene"},
            "content_hash": "content",
            "catalog_revision": "revision",
        },
    )

    def load_cube_definition(
        self,
        cube_id: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return the configured latest definition."""

        return self.load_cube_definition_version(
            cube_id,
            self.definition.version,
            cube_load_trace_id=cube_load_trace_id,
        )

    def load_cube_definition_version(
        self,
        cube_id: str,
        version: str,
        *,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeDefinition:
        """Return the configured exact definition."""

        _ = cube_load_trace_id
        if cube_id != self.definition.cube_id or version != self.definition.version:
            raise RuntimeError("Unexpected cube identity.")
        return self.definition

    def build_loaded_cube_runtime(
        self,
        cube_id: str,
        alias_name: str,
        *,
        buffer_patch: object | None,
        runtime_state: object | None,
        loaded_cube_definition: LoadedCubeDefinition | None = None,
        cube_load_trace_id: str = "",
    ) -> LoadedCubeRuntime:
        """Build one deterministic hydrated cube runtime."""

        _ = buffer_patch, runtime_state, cube_load_trace_id
        definition = loaded_cube_definition or self.definition
        cube_state = CubeState(
            cube_id=cube_id,
            version=definition.version,
            alias=alias_name,
            original_cube=definition.graph,
            buffer=deepcopy(definition.graph),
            display_name=definition.display_name,
            ui=deepcopy(definition.ui_payload),
        )
        return LoadedCubeRuntime(
            cube_id=cube_id,
            version=definition.version,
            display_name=definition.display_name,
            cube_definition=definition.graph,
            cube_buffer=cube_state.buffer,
            cube_state=cube_state,
            ui_payload=definition.ui_payload,
        )


class HarnessNodeBehaviorService:
    """Prepare empty cube runtime behavior state."""

    def prepare_runtime_state(
        self,
        loaded_cube: LoadedCubeDefinition,
        alias_name: str,
    ) -> NodeBehaviorRuntimeState:
        """Return deterministic no-op behavior state."""

        _ = loaded_cube, alias_name
        return NodeBehaviorRuntimeState()


class HarnessNodeDefinitionGateway:
    """Return live definitions for both fixture node classes."""

    definitions: dict[str, dict[str, object]] = {
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {}]}}},
        "KSampler": {"input": {"required": {"seed": ["INT", {}]}}},
    }

    def get_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one deterministic live node definition."""

        return self.definitions[node_class]

    def get_required_node_definition(self, node_class: str) -> dict[str, object]:
        """Return one deterministic required live node definition."""

        return self.get_node_definition(node_class)


class HarnessMaterializationPort:
    """Record workflow snapshots delivered through materialization."""

    def __init__(self) -> None:
        """Initialize materialization observations."""

        self.workflows: dict[str, WorkflowSnapshot] = {}
        self.projected_workflow_id = ""
        self.reset_calls = 0

    def reset_restored_workspace(self) -> None:
        """Record one workspace reset."""

        self.reset_calls += 1

    def add_restored_workflow(
        self, snapshot: WorkflowSnapshot, *, activate: bool
    ) -> None:
        """Retain the exact restored workflow state."""

        _ = activate
        self.workflows[snapshot.workflow_id] = snapshot

    def load_restored_input_image(self, path: Path) -> object | None:
        """Return no image payloads for the image-free fixture."""

        _ = path
        return None

    def restore_input_image(
        self, reference: InputImageReference, image: object
    ) -> None:
        """Reject unexpected image restoration."""

        raise AssertionError((reference, image))

    def restore_input_mask(self, reference: InputMaskReference) -> bool:
        """Reject unexpected mask restoration."""

        raise AssertionError(reference)

    def load_restored_output_image(self, path: Path) -> object | None:
        """Return no output payloads for the image-free fixture."""

        _ = path
        return None

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: object,
    ) -> None:
        """Reject unexpected output restoration."""

        raise AssertionError((workflow_id, reference, image, image_meta))

    def project_restored_workflow(self, workflow_id: str) -> None:
        """Record the active restored workflow projection."""

        self.projected_workflow_id = workflow_id

    def project_restored_settings(self) -> None:
        """Reject unexpected settings projection."""

        raise AssertionError("settings projection was not expected")

    def apply_restored_shell_layout(self, snapshot: object | None) -> None:
        """Accept the restored shell layout."""

        _ = snapshot


__all__ = ["HeadlessWorkspaceRestoreHarness"]
