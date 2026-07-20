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

"""Rewrite execution payload asset paths through a Comfy target staging boundary."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

import copy
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from substitute.application.ports.comfy_asset_stager import ComfyAssetStager
from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.application.workflows.workflow_asset_service import WorkflowAssetService
from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingPlanService,
    InputAssetStagingTarget,
)
from substitute.application.workflows.input_asset_endpoint_service import (
    InputAssetEndpointService,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.common import JsonObject, WorkflowId
from substitute.domain.generation import AssetStagingFailure, ComfyStagedAsset
from substitute.domain.workflow import (
    InputAssetRole,
    ProjectMaskAssetRef,
    WorkflowState,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
)

_LOGGER = get_logger("application.generation.asset_staging_service")
_LOAD_IMAGE_CLASSES = frozenset({"LoadImage", "LoadImageMask"})
_SAFE_SUBFOLDER_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class ComfyAssetStagingResult:
    """Capture payload and diagnostics after generation asset staging."""

    workflow_payload: JsonObject
    staged_assets: tuple[ComfyStagedAsset, ...]
    failures: tuple[AssetStagingFailure, ...]


class ComfyAssetStagingService:
    """Own generation-time rewriting of local assets for the active Comfy target."""

    def __init__(
        self,
        *,
        stager: ComfyAssetStager,
        input_asset_staging_plan_service: InputAssetStagingPlanService | None = None,
    ) -> None:
        """Capture the concrete target stager used for source files."""

        self._stager = stager
        self._input_asset_staging_plan_service = (
            input_asset_staging_plan_service
            or InputAssetStagingPlanService(
                InputAssetEndpointService(WorkflowNodeDefinitionService()),
                WorkflowGraphSectionService(),
            )
        )
        self._projects_dir: Path | None = None

    @classmethod
    def with_projects_dir(
        cls,
        *,
        stager: ComfyAssetStager,
        projects_dir: Path,
        input_asset_staging_plan_service: InputAssetStagingPlanService | None = None,
    ) -> "ComfyAssetStagingService":
        """Build a staging service that can resolve project-relative mask assets."""

        service = cls(
            stager=stager,
            input_asset_staging_plan_service=input_asset_staging_plan_service,
        )
        service._projects_dir = projects_dir
        return service

    @property
    def stager(self) -> ComfyAssetStager:
        """Return the target stager composed for this service."""

        return self._stager

    def stage_payload(
        self,
        *,
        workflow_payload: JsonObject,
        workflow_id: WorkflowId,
        workflow_name: str,
        workflow: object | None = None,
    ) -> ComfyAssetStagingResult:
        """Stage local LoadImage assets and return an execution-only payload copy."""

        staged_payload = copy.deepcopy(workflow_payload)
        prompt = _prompt_nodes(staged_payload)
        if prompt is None:
            return ComfyAssetStagingResult(
                workflow_payload=staged_payload,
                staged_assets=(),
                failures=(),
            )

        staged_assets: list[ComfyStagedAsset] = []
        failures: list[AssetStagingFailure] = []
        target_subfolder = (
            f"substitute/{_safe_subfolder_component(workflow_id or workflow_name)}"
        )

        targets = self._staging_targets(workflow=workflow, prompt=prompt)
        for target in targets:
            node_id = target.executable_node_id
            node_data = prompt.get(node_id)
            if not isinstance(node_data, dict):
                continue
            node_class = node_data.get("class_type")
            inputs = node_data.get("inputs", {})
            if not isinstance(inputs, dict):
                continue
            image_value = inputs.get(target.field_key)
            if not isinstance(image_value, str) or not image_value:
                failures.append(
                    AssetStagingFailure(
                        node_id=str(node_id),
                        node_class=str(node_class),
                        input_name=target.field_key,
                        source_value=image_value
                        if isinstance(image_value, str)
                        else "",
                        message=app_text("Required image input has no selected image."),
                    )
                )
                continue
            source_path = self._source_path_for_load_image_value(
                image_value=image_value,
                target=target,
                workflow_name=workflow_name,
                workflow=workflow,
            )
            if source_path is None:
                log_debug(
                    _LOGGER,
                    "Skipping Comfy load-image asset staging",
                    workflow_id=workflow_id,
                    node_id=str(node_id),
                    node_class=str(node_class),
                    image_value=image_value,
                    skip_reason="comfy_input_name",
                )
                continue
            if not source_path.exists():
                failures.append(
                    AssetStagingFailure(
                        node_id=str(node_id),
                        node_class=str(node_class),
                        input_name=target.field_key,
                        source_value=image_value,
                        message=app_text("Referenced local image file does not exist."),
                    )
                )
                continue
            try:
                staged_asset = self._stager.stage_file_for_load_image(
                    source_path=source_path,
                    target_subfolder=target_subfolder,
                    content_hash=_file_sha256(source_path),
                )
            except Exception as error:
                log_exception(
                    _LOGGER,
                    "Failed to stage Comfy load-image asset",
                    workflow_id=workflow_id,
                    node_id=str(node_id),
                    node_class=str(node_class),
                    source_path=str(source_path),
                    error=error,
                )
                failures.append(
                    AssetStagingFailure(
                        node_id=str(node_id),
                        node_class=str(node_class),
                        input_name=target.field_key,
                        source_value=image_value,
                        message=str(error),
                    )
                )
                continue
            inputs[target.field_key] = staged_asset.execution_value
            if self._should_use_project_mask_color_channel(
                image_value=image_value,
                target=target,
                source_path=source_path,
                workflow_name=workflow_name,
                workflow=workflow,
            ):
                old_channel = inputs.get("channel")
                if old_channel != "red":
                    inputs["channel"] = "red"
                    log_debug(
                        _LOGGER,
                        "Normalized Substitute project mask channel for Comfy execution",
                        workflow_id=workflow_id,
                        node_id=str(node_id),
                        node_class=str(node_class),
                        asset_ref_kind="project_mask",
                        source_path=str(source_path),
                        old_channel=old_channel,
                        new_channel="red",
                    )
            staged_assets.append(staged_asset)
            log_debug(
                _LOGGER,
                "Staged Comfy load-image asset",
                workflow_id=workflow_id,
                node_id=str(node_id),
                node_class=str(node_class),
                source_path=str(source_path),
                execution_value=staged_asset.execution_value,
                operation=staged_asset.operation,
            )

        return ComfyAssetStagingResult(
            workflow_payload=staged_payload,
            staged_assets=tuple(staged_assets),
            failures=tuple(failures),
        )

    def _staging_targets(
        self,
        *,
        workflow: object | None,
        prompt: Mapping[str, object],
    ) -> tuple[InputAssetStagingTarget, ...]:
        """Return semantic targets or exact built-in fallbacks without workflow state."""

        if isinstance(workflow, WorkflowState):
            return self._input_asset_staging_plan_service.targets_for_prompt(
                workflow,
                prompt,
            )
        targets: list[InputAssetStagingTarget] = []
        for raw_node_id, raw_node in prompt.items():
            if not isinstance(raw_node, Mapping):
                continue
            class_type = raw_node.get("class_type")
            if class_type not in _LOAD_IMAGE_CLASSES:
                continue
            node_id = str(raw_node_id)
            targets.append(
                InputAssetStagingTarget(
                    executable_node_id=node_id,
                    section_key="",
                    node_name=node_id,
                    field_key="image",
                    role=(
                        InputAssetRole.MASK
                        if class_type == "LoadImageMask"
                        else InputAssetRole.IMAGE
                    ),
                )
            )
        return tuple(targets)

    def _source_path_for_load_image_value(
        self,
        *,
        image_value: str,
        target: InputAssetStagingTarget,
        workflow_name: str,
        workflow: object | None,
    ) -> Path | None:
        """Return a filesystem source path for local or project asset values."""

        if _looks_like_local_path(image_value):
            return Path(image_value)
        if target.role is not InputAssetRole.MASK or self._projects_dir is None:
            return None
        candidate = self._projects_dir / workflow_name / "masks" / image_value
        if candidate.exists():
            log_debug(
                _LOGGER,
                "Resolved project mask asset for Comfy staging",
                workflow_name=workflow_name,
                image_value=image_value,
                source_path=str(candidate),
                asset_ref_kind="project_mask",
            )
            return candidate
        if self._is_project_mask_asset(
            workflow=workflow,
            target=target,
        ):
            return candidate
        return None

    def _is_project_mask_asset(
        self,
        *,
        workflow: object | None,
        target: InputAssetStagingTarget,
    ) -> bool:
        """Return whether compiled metadata points to a project mask asset ref."""

        if not isinstance(workflow, WorkflowState):
            return False
        asset_ref = WorkflowAssetService().input_mask_asset_ref(
            workflow,
            section_key=target.section_key,
            node_name=target.node_name,
            field_key=target.field_key,
        )
        return isinstance(asset_ref, ProjectMaskAssetRef)

    def _should_use_project_mask_color_channel(
        self,
        *,
        image_value: str,
        target: InputAssetStagingTarget,
        source_path: Path,
        workflow_name: str,
        workflow: object | None,
    ) -> bool:
        """Return whether a staged LoadImageMask is a Substitute grayscale mask."""

        if target.role is not InputAssetRole.MASK:
            return False
        if self._is_project_mask_asset(workflow=workflow, target=target):
            return True
        if self._projects_dir is None:
            return False
        project_mask_dir = (self._projects_dir / workflow_name / "masks").resolve()
        resolved_source = source_path.resolve()
        try:
            resolved_source.relative_to(project_mask_dir)
        except ValueError:
            return False
        return source_path.name == image_value or resolved_source.exists()


def _prompt_nodes(workflow_payload: JsonObject) -> dict[str, object] | None:
    """Return mutable executable prompt nodes from a copied workflow payload."""

    nodes = executable_prompt_nodes(workflow_payload)
    return nodes if isinstance(nodes, dict) else None


def _looks_like_local_path(value: str) -> bool:
    """Return whether a graph value appears to reference a filesystem path."""

    path = Path(value)
    return path.is_absolute() or "\\" in value or "/" in value


def _file_sha256(path: Path) -> str:
    """Return the sha256 digest for one source file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_subfolder_component(value: str) -> str:
    """Return a Comfy-safe staging subfolder component."""

    cleaned = _SAFE_SUBFOLDER_RE.sub("_", value.strip()).strip("._")
    return cleaned or "workflow"


__all__ = ["ComfyAssetStagingResult", "ComfyAssetStagingService"]
