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

"""Own workflow graph asset associations and their persisted metadata."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from substitute.domain.workflow import WorkflowState
from substitute.domain.workflow.asset_models import (
    ComfyInputAssetRef,
    LocalFileAssetRef,
    ProjectAssetRef,
    ProjectMaskAssetRef,
    WorkflowAssetRef,
    workflow_asset_ref_authoring_value,
    workflow_asset_ref_from_json,
    workflow_asset_ref_to_json,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning,
    log_debug,
)
from substitute.shared.util.path_safety import (
    ensure_within_root,
    validate_top_level_name,
)

_LOGGER = get_logger("application.workflows.workflow_asset_service")
_ASSET_REFS_KEY = "asset_refs"
_INPUT_IMAGES_KEY = "input_images"
_INPUT_MASKS_KEY = "input_masks"


@dataclass(frozen=True, slots=True)
class CubeAssetAssociationCopyResult:
    """Summarize durable asset associations copied to a duplicate cube."""

    input_image_count: int
    input_mask_count: int


class WorkflowAssetService:
    """Own durable asset references attached to workflow graph inputs."""

    def duplicate_cube_associations(
        self,
        workflow: WorkflowState,
        *,
        source_alias: str,
        target_alias: str,
    ) -> CubeAssetAssociationCopyResult:
        """Copy source-alias image and mask references to a duplicate alias."""

        image_count = self._duplicate_alias_associations(
            workflow,
            collection_key=_INPUT_IMAGES_KEY,
            source_alias=source_alias,
            target_alias=target_alias,
        )
        mask_count = self._duplicate_alias_associations(
            workflow,
            collection_key=_INPUT_MASKS_KEY,
            source_alias=source_alias,
            target_alias=target_alias,
        )
        log_info(
            _LOGGER,
            "Duplicated cube asset associations",
            source_alias=source_alias,
            target_alias=target_alias,
            input_image_count=image_count,
            input_mask_count=mask_count,
        )
        return CubeAssetAssociationCopyResult(
            input_image_count=image_count,
            input_mask_count=mask_count,
        )

    @staticmethod
    def _duplicate_alias_associations(
        workflow: WorkflowState,
        *,
        collection_key: str,
        source_alias: str,
        target_alias: str,
    ) -> int:
        """Copy one alias-owned metadata collection and return its copy count."""

        asset_refs = workflow.metadata.get(_ASSET_REFS_KEY)
        if not isinstance(asset_refs, dict):
            return 0
        collection = asset_refs.get(collection_key)
        if not isinstance(collection, dict):
            return 0
        source_prefix = f"{source_alias}:"
        copies = {
            f"{target_alias}:{key.removeprefix(source_prefix)}": deepcopy(value)
            for key, value in tuple(collection.items())
            if key.startswith(source_prefix)
        }
        collection.update(copies)
        return len(copies)

    def associate_input_image(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        asset_ref: WorkflowAssetRef,
    ) -> bool:
        """Associate one image input node with an asset reference and buffer value."""

        return self._associate_node_asset(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=asset_ref,
            collection_key=_INPUT_IMAGES_KEY,
            log_subject="input image",
        )

    def associate_input_mask(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        asset_ref: WorkflowAssetRef,
    ) -> bool:
        """Associate one mask input node with an asset reference and buffer value."""

        return self._associate_node_asset(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=asset_ref,
            collection_key=_INPUT_MASKS_KEY,
            log_subject="input mask",
        )

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one mask input node with a Substitute-owned project mask."""

        return self.associate_input_mask(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=ProjectMaskAssetRef(relative_path=str(relative_path)),
        )

    def associate_project_input_image(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one image input node with a Substitute-owned project asset."""

        return self.associate_input_image(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=ProjectAssetRef(relative_path=str(relative_path)),
        )

    def associate_comfy_input_image(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        name: str,
    ) -> bool:
        """Associate one image input node with a Comfy input namespace asset."""

        return self.associate_input_image(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=ComfyInputAssetRef(name=name),
        )

    def associate_comfy_input_mask(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        name: str,
    ) -> bool:
        """Associate one mask input node with a Comfy input namespace asset."""

        return self.associate_input_mask(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=ComfyInputAssetRef(name=name),
        )

    def _associate_node_asset(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        asset_ref: WorkflowAssetRef,
        collection_key: str,
        log_subject: str,
    ) -> bool:
        """Associate one LoadImage-style node with a typed asset reference."""

        cube_state = workflow.cubes.get(cube_alias)
        if cube_state is None:
            log_warning(
                _LOGGER,
                f"Cannot associate {log_subject} because cube is missing",
                cube_alias=cube_alias,
                node_name=node_name,
                asset_ref_kind=asset_ref.kind,
                target_value=workflow_asset_ref_authoring_value(asset_ref),
            )
            return False
        nodes = cube_state.buffer.get("nodes", {})
        if not isinstance(nodes, dict):
            log_warning(
                _LOGGER,
                f"Cannot associate {log_subject} because cube nodes are unavailable",
                cube_alias=cube_alias,
                node_name=node_name,
                asset_ref_kind=asset_ref.kind,
                target_value=workflow_asset_ref_authoring_value(asset_ref),
            )
            return False
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            log_warning(
                _LOGGER,
                f"Cannot associate {log_subject} because node is missing",
                cube_alias=cube_alias,
                node_name=node_name,
                asset_ref_kind=asset_ref.kind,
                target_value=workflow_asset_ref_authoring_value(asset_ref),
            )
            return False
        inputs = node.setdefault("inputs", {})
        if not isinstance(inputs, dict):
            log_warning(
                _LOGGER,
                f"Cannot associate {log_subject} because node inputs are invalid",
                cube_alias=cube_alias,
                node_name=node_name,
                asset_ref_kind=asset_ref.kind,
                target_value=workflow_asset_ref_authoring_value(asset_ref),
                input_type=type(inputs).__name__,
            )
            return False

        old_value = inputs.get("image")
        new_value = workflow_asset_ref_authoring_value(asset_ref)
        inputs["image"] = new_value
        self._asset_metadata(workflow, collection_key)[
            self._association_key(cube_alias, node_name)
        ] = workflow_asset_ref_to_json(asset_ref)
        cube_state.dirty = True
        log_debug(
            _LOGGER,
            f"Associated workflow {log_subject} asset",
            cube_alias=cube_alias,
            node_name=node_name,
            old_image_value=old_value,
            new_image_value=new_value,
            asset_ref_kind=asset_ref.kind,
            cube_dirty=cube_state.dirty,
        )
        return True

    def associate_local_input_image(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        image_path: Path | str,
    ) -> bool:
        """Associate one image input node with a user-selected local file."""

        return self.associate_input_image(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=LocalFileAssetRef.from_path(image_path),
        )

    def associate_local_input_mask(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        mask_path: Path | str,
    ) -> bool:
        """Associate one mask input node with a user-selected local mask file."""

        return self.associate_input_mask(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            asset_ref=LocalFileAssetRef.from_path(mask_path),
        )

    def input_image_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return the durable asset reference for one input node when available."""

        return self._node_asset_ref(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            collection_key=_INPUT_IMAGES_KEY,
            log_subject="input image",
        )

    def input_mask_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
    ) -> WorkflowAssetRef | None:
        """Return the durable asset reference for one input mask node when available."""

        return self._node_asset_ref(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
            collection_key=_INPUT_MASKS_KEY,
            log_subject="input mask",
        )

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        cube_alias: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve the display path for one input mask from authoritative asset state."""

        asset_ref = self.input_mask_asset_ref(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
        )
        if isinstance(asset_ref, ProjectMaskAssetRef):
            try:
                resolved_path = _resolve_mask_path(
                    workflow_name=workflow_name,
                    path_from_buffer=asset_ref.relative_path,
                    projects_dir=projects_dir,
                )
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Failed to resolve input mask path from project mask asset",
                    workflow_name=workflow_name,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    mask_path=asset_ref.relative_path,
                    asset_ref_kind=asset_ref.kind,
                    error=error,
                )
                return None
            log_debug(
                _LOGGER,
                "Resolved input mask path from workflow asset metadata",
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                path=str(resolved_path),
                asset_ref_kind=asset_ref.kind,
            )
            return resolved_path
        if isinstance(asset_ref, LocalFileAssetRef):
            log_debug(
                _LOGGER,
                "Resolved input mask path from local file asset metadata",
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                path=asset_ref.path,
                asset_ref_kind=asset_ref.kind,
            )
            return Path(asset_ref.path)
        if isinstance(asset_ref, ProjectAssetRef):
            try:
                resolved_path = _resolve_project_asset_path(
                    workflow_name=workflow_name,
                    relative_path=asset_ref.relative_path,
                    projects_dir=projects_dir,
                )
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Failed to resolve input mask path from project asset metadata",
                    workflow_name=workflow_name,
                    cube_alias=cube_alias,
                    node_name=node_name,
                    project_path=asset_ref.relative_path,
                    asset_ref_kind=asset_ref.kind,
                    error=error,
                )
                return None
            log_debug(
                _LOGGER,
                "Resolved input mask path from project asset metadata",
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                path=str(resolved_path),
                asset_ref_kind=asset_ref.kind,
            )
            return resolved_path
        if isinstance(asset_ref, ComfyInputAssetRef):
            log_info(
                _LOGGER,
                "Skipping input mask path resolution for Comfy input asset",
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                asset_ref_kind=asset_ref.kind,
                comfy_input_name=asset_ref.name,
            )
            return None

        path_from_buffer = self._buffer_image_value(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
        )
        if path_from_buffer is None:
            return None
        try:
            resolved_path = _resolve_mask_path(
                workflow_name=workflow_name,
                path_from_buffer=path_from_buffer,
                projects_dir=projects_dir,
            )
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Failed to resolve input mask path from workflow buffer",
                workflow_name=workflow_name,
                cube_alias=cube_alias,
                node_name=node_name,
                mask_path=path_from_buffer,
                error=error,
            )
            return None
        log_debug(
            _LOGGER,
            "Resolved input mask path from workflow buffer",
            workflow_name=workflow_name,
            cube_alias=cube_alias,
            node_name=node_name,
            path=str(resolved_path),
        )
        return resolved_path

    def _node_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
        collection_key: str,
        log_subject: str,
    ) -> WorkflowAssetRef | None:
        """Return a typed asset reference from metadata or current buffer values."""

        key = self._association_key(cube_alias, node_name)
        asset_refs = workflow.metadata.get(_ASSET_REFS_KEY, {})
        if isinstance(asset_refs, dict):
            collection = asset_refs.get(collection_key, {})
            if isinstance(collection, dict):
                payload = collection.get(key)
                if isinstance(payload, Mapping):
                    try:
                        return workflow_asset_ref_from_json(payload)
                    except ValueError as error:
                        log_warning(
                            _LOGGER,
                            f"Ignoring invalid workflow {log_subject} asset metadata",
                            cube_alias=cube_alias,
                            node_name=node_name,
                            error=error,
                        )

        authoring_value = self._buffer_image_value(
            workflow,
            cube_alias=cube_alias,
            node_name=node_name,
        )
        if authoring_value is None:
            return None
        if collection_key == _INPUT_MASKS_KEY:
            return None
        if _looks_like_local_path(authoring_value):
            return LocalFileAssetRef(path=authoring_value)
        return ComfyInputAssetRef(name=authoring_value)

    def _input_image_metadata(self, workflow: WorkflowState) -> dict[str, object]:
        """Return mutable metadata storage for input-image asset references."""

        return self._asset_metadata(workflow, _INPUT_IMAGES_KEY)

    def _input_mask_metadata(self, workflow: WorkflowState) -> dict[str, object]:
        """Return mutable metadata storage for input-mask asset references."""

        return self._asset_metadata(workflow, _INPUT_MASKS_KEY)

    @staticmethod
    def _asset_metadata(
        workflow: WorkflowState, collection_key: str
    ) -> dict[str, object]:
        """Return mutable metadata storage for one asset-reference collection."""

        asset_refs = workflow.metadata.setdefault(_ASSET_REFS_KEY, {})
        if not isinstance(asset_refs, dict):
            asset_refs = {}
            workflow.metadata[_ASSET_REFS_KEY] = asset_refs
        collection = asset_refs.setdefault(collection_key, {})
        if not isinstance(collection, dict):
            collection = {}
            asset_refs[collection_key] = collection
        return collection

    @staticmethod
    def _buffer_image_value(
        workflow: WorkflowState,
        *,
        cube_alias: str,
        node_name: str,
    ) -> str | None:
        """Return the current graph-buffer image value for one input node."""

        cube_state = workflow.cubes.get(cube_alias)
        if cube_state is None:
            return None
        nodes = cube_state.buffer.get("nodes", {})
        if not isinstance(nodes, dict):
            return None
        node = nodes.get(node_name)
        if not isinstance(node, dict):
            return None
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            return None
        value = inputs.get("image")
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _association_key(cube_alias: str, node_name: str) -> str:
        """Return the persisted metadata key for one cube node input."""

        return f"{cube_alias}:{node_name}"


def _looks_like_local_path(value: str) -> bool:
    """Return whether a graph value appears to reference a filesystem path."""

    path = Path(value)
    return path.is_absolute() or "\\" in value or "/" in value


def _resolve_mask_path(
    *,
    workflow_name: str,
    path_from_buffer: str,
    projects_dir: Path,
) -> Path:
    """Resolve an input-mask authoring value to a safe display path."""

    raw_path = Path(path_from_buffer)
    if raw_path.is_absolute():
        return raw_path

    safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
    candidate = projects_dir / safe_workflow_name / "masks" / raw_path
    return ensure_within_root(
        candidate,
        root_path=projects_dir,
        subject="Mask path",
    )


def _resolve_project_asset_path(
    *,
    workflow_name: str,
    relative_path: str,
    projects_dir: Path,
) -> Path:
    """Resolve a workflow-relative project asset path safely."""

    raw_path = Path(relative_path)
    if raw_path.is_absolute():
        return raw_path

    safe_workflow_name = validate_top_level_name(workflow_name, subject="Workflow")
    candidate = projects_dir / safe_workflow_name / raw_path
    return ensure_within_root(
        candidate,
        root_path=projects_dir,
        subject="Project asset path",
    )


__all__ = ["WorkflowAssetService"]
