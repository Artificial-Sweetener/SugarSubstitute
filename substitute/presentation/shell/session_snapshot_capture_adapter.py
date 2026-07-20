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

"""Adapt live shell widgets into the session snapshot capture port."""

from __future__ import annotations

from substitute.presentation.workflows.workflow_tabs_view import (
    workflow_tab_source_text,
)

from pathlib import Path
from typing import Any, cast

from substitute.domain.workflow import (
    ComfyInputAssetRef,
    LocalFileAssetRef,
    ProjectAssetRef,
    ProjectMaskAssetRef,
    WorkflowState,
)
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.shell.session_snapshot_capture_adapter")


class SessionSnapshotCaptureAdapter:
    """Read live shell state needed by session snapshot capture."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose live state should be adapted."""

        self._shell = shell

    def workflow_ids_in_order(self) -> tuple[str, ...]:
        """Return workflow ids in visual tab order for session capture."""

        return tuple(self._shell.workflow_tabbar.workflow_ids_in_order())

    def active_workspace_route(self) -> str:
        """Return the currently projected workspace route for session capture."""

        return str(getattr(self._shell, "_active_workspace_route", ""))

    def active_workflow_id(self) -> str:
        """Return the workflow active beneath any projected workspace route."""

        return str(
            getattr(self._shell.workflow_session_service, "active_workflow_id", "")
        )

    def workflow_state(self, workflow_id: str) -> WorkflowState | None:
        """Return workflow state for one workflow id."""

        return cast(
            WorkflowState | None,
            self._shell.workflow_session_service.get_workflow(workflow_id),
        )

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return the tab label for one workflow id."""

        item = self._shell.workflow_tabbar.itemMap.get(workflow_id)
        if item is None:
            return workflow_id
        return workflow_tab_source_text(item)

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return the active cube alias for one workflow."""

        cube_stack = self._shell.cube_stacks.get(workflow_id)
        if cube_stack is None:
            log_debug(
                _LOGGER,
                "session snapshot active cube alias missing stack",
                workflow_id=workflow_id,
            )
            return None
        index = cube_stack.currentIndex()
        if index < 0 or index >= cube_stack.count():
            log_debug(
                _LOGGER,
                "session snapshot active cube alias invalid index",
                workflow_id=workflow_id,
                current_index=index,
                stack_count=cube_stack.count(),
            )
            return None
        alias = str(cube_stack.tabItem(index).routeKey())
        log_debug(
            _LOGGER,
            "session snapshot active cube alias captured",
            workflow_id=workflow_id,
            current_index=index,
            stack_count=cube_stack.count(),
            active_cube_alias=alias,
        )
        return alias

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return restorable editor viewport state for one workflow."""

        editor_panel = self._shell.editor_panels.get(workflow_id)
        if editor_panel is None:
            log_info(
                _LOGGER,
                "session snapshot editor viewport skipped missing panel",
                workflow_id=workflow_id,
            )
            return None
        try:
            scroll = getattr(editor_panel, "scroll")
            scrollbar = scroll.verticalScrollBar()
            scroll_value = max(0, int(scrollbar.value()))
            scroll_maximum = max(0, int(scrollbar.maximum()))
            anchor_cube_alias = self.active_cube_alias(workflow_id)
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to capture session editor viewport snapshot",
                workflow_id=workflow_id,
                error=repr(error),
            )
            return None
        log_debug(
            _LOGGER,
            "session snapshot editor viewport captured",
            workflow_id=workflow_id,
            scroll_value=scroll_value,
            scroll_maximum=scroll_maximum,
            anchor_cube_alias=anchor_cube_alias,
        )
        return EditorViewportSnapshot(
            scroll_value=scroll_value,
            scroll_maximum=scroll_maximum,
            anchor_cube_alias=anchor_cube_alias,
        )

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return restorable input image references for one workflow."""

        del workflow_id
        references: list[InputImageReference] = []
        input_key_map = getattr(workflow.canvas, "input_key_map", {})
        if not isinstance(input_key_map, dict):
            return ()
        for sequence, image_id in enumerate(
            input_key_map.values(),
            start=1,
        ):
            path = self._shell.input_canvas_state_service.input_image_path(image_id)
            if path is None:
                continue
            references.append(
                InputImageReference(
                    image_id=str(image_id),
                    path=path,
                    sequence=sequence,
                )
            )
        return tuple(references)

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return restorable input mask references for one workflow."""

        references: list[InputMaskReference] = []
        workflow_name = self.workflow_tab_label(workflow_id)
        mask_associations = getattr(workflow.canvas, "mask_associations", {})
        mask_to_image_map = getattr(workflow.canvas, "mask_to_image_map", {})
        if not isinstance(mask_associations, dict) or not isinstance(
            mask_to_image_map,
            dict,
        ):
            return ()
        for association_key, mask_id in mask_associations.items():
            if not isinstance(association_key, tuple) or len(association_key) != 2:
                continue
            cube_alias = str(association_key[0])
            node_name = str(association_key[1])
            image_id = mask_to_image_map.get(mask_id)
            if image_id is None:
                continue
            asset_ref = self._shell.workflow_input_canvas_service.input_mask_asset_ref(
                workflow,
                section_key=cube_alias,
                node_name=node_name,
            )
            path = self.capture_path_for_asset_ref(
                asset_ref,
                workflow_name=workflow_name,
            )
            if path is None:
                continue
            references.append(
                InputMaskReference(
                    mask_id=str(mask_id),
                    image_id=str(image_id),
                    path=path,
                    association_key=(cube_alias, node_name),
                )
            )
        return tuple(references)

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return restorable output image references for one workflow."""

        del workflow_id
        references: list[OutputImageReference] = []
        for sequence, image_id in enumerate(workflow.output_image_uuids, start=1):
            image_meta = self._shell.canvas_image_registry.metadata_for(image_id)
            if image_meta is None or not image_meta.path:
                continue
            path = Path(image_meta.path)
            references.append(
                OutputImageReference(
                    image_id=str(image_id),
                    path=path,
                    metadata=ImageMetaSnapshot(
                        workflow_name=image_meta.workflow_name,
                        cube_name=image_meta.cube_name,
                        image_number=image_meta.image_number,
                        suffix=image_meta.suffix,
                        path=path,
                        source_key=image_meta.source_key,
                        source_label=image_meta.source_label,
                        node_id=image_meta.node_id,
                        generation_run_id=image_meta.generation_run_id,
                        prompt_id=image_meta.prompt_id,
                        client_id=image_meta.client_id,
                        list_index=image_meta.list_index,
                        batch_index=image_meta.batch_index,
                        scene_run_id=image_meta.scene_run_id or None,
                        scene_key=image_meta.scene_key or None,
                        scene_title=image_meta.scene_title or None,
                        scene_order=image_meta.scene_order,
                        scene_count=image_meta.scene_count,
                        width=image_meta.width,
                        height=image_meta.height,
                        cube_execution_duration_ms=(
                            image_meta.cube_execution_duration_ms
                        ),
                    ),
                    sequence=sequence,
                )
            )
        return tuple(references)

    def shell_layout_snapshot(self) -> ShellLayoutSnapshot | None:
        """Return restorable shell layout state from the layout controller."""

        return cast(
            ShellLayoutSnapshot | None,
            self._shell.shell_layout_restore_controller.capture_shell_layout_snapshot(),
        )

    def capture_path_for_asset_ref(
        self,
        asset_ref: object,
        *,
        workflow_name: str,
    ) -> Path | None:
        """Resolve a workflow asset reference to a restorable local path."""

        if isinstance(asset_ref, LocalFileAssetRef):
            return Path(asset_ref.path)
        if isinstance(asset_ref, ProjectMaskAssetRef):
            projects_dir = Path(self._shell.path_bundle.projects_dir)
            return projects_dir / workflow_name / "masks" / asset_ref.relative_path
        if isinstance(asset_ref, ProjectAssetRef):
            projects_dir = Path(self._shell.path_bundle.projects_dir)
            return projects_dir / workflow_name / asset_ref.relative_path
        if isinstance(asset_ref, ComfyInputAssetRef):
            return None
        return None


def snapshot_capture_adapter_for(shell: Any) -> SessionSnapshotCaptureAdapter:
    """Return the composed session snapshot capture adapter for a shell."""

    adapter = getattr(shell, "session_snapshot_capture_adapter", None)
    if isinstance(adapter, SessionSnapshotCaptureAdapter):
        return adapter
    adapter = SessionSnapshotCaptureAdapter(shell)
    setattr(shell, "session_snapshot_capture_adapter", adapter)
    return adapter


__all__ = [
    "SessionSnapshotCaptureAdapter",
    "snapshot_capture_adapter_for",
]
