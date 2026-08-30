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

"""Resolve authored scalar and ordered asset references to local source paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from substitute.application.generation.input_asset_staging_plan_service import (
    InputAssetStagingTarget,
)
from substitute.application.workflows.workflow_asset_service import (
    WorkflowAssetService,
)
from substitute.domain.workflow import (
    ProjectMaskAssetRef,
    WorkflowState,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.generation.input_asset_source_resolver")


@dataclass(frozen=True, slots=True)
class InputAssetSourceResolution:
    """Distinguish absent metadata from an asset that intentionally needs no staging."""

    handled: bool
    path: Path | None


@dataclass(frozen=True, slots=True)
class OrderedInputAssetSource:
    """Pair one authoritative ordered asset value with its resolved path."""

    source_value: str
    path: Path | None


class InputAssetSourceResolver:
    """Own typed workflow-asset and legacy path resolution for generation staging."""

    def __init__(self, projects_dir: Path | None = None) -> None:
        """Store the optional Substitute project root used by durable references."""

        self._projects_dir = projects_dir

    def scalar_source(
        self,
        *,
        image_value: str,
        target: InputAssetStagingTarget,
        workflow_name: str,
        workflow: object | None,
    ) -> Path | None:
        """Resolve one scalar upload field from typed metadata or legacy value."""

        typed_source = self._typed_scalar_source(
            target=target,
            workflow_name=workflow_name,
            workflow=workflow,
        )
        if typed_source.handled:
            return typed_source.path
        if _looks_like_local_path(image_value):
            return Path(image_value)
        if target.role.value != "mask" or self._projects_dir is None:
            return None
        candidate = self._projects_dir / workflow_name / "masks" / image_value
        if candidate.exists() or self.is_project_mask(workflow=workflow, target=target):
            log_debug(
                _LOGGER,
                "Resolved legacy project mask asset for generation staging",
                workflow_name=workflow_name,
                image_value=image_value,
                source_path=str(candidate),
            )
            return candidate
        return None

    def ordered_sources(
        self,
        *,
        values: list[str],
        workflow_name: str,
    ) -> tuple[OrderedInputAssetSource, ...]:
        """Resolve the compiler-authored ordered values without another authority."""

        return tuple(
            OrderedInputAssetSource(
                source_value=value,
                path=(
                    Path(value)
                    if Path(value).is_absolute()
                    else self._project_mask_path(
                        workflow_name,
                        value,
                    )
                ),
            )
            for value in values
        )

    def is_project_mask(
        self,
        *,
        workflow: object | None,
        target: InputAssetStagingTarget,
    ) -> bool:
        """Return whether a scalar target owns a typed Substitute project mask."""

        if not isinstance(workflow, WorkflowState):
            return False
        asset_ref = WorkflowAssetService().input_mask_asset_ref(
            workflow,
            section_key=target.section_key,
            node_name=target.node_name,
            field_key=target.field_key,
        )
        return isinstance(asset_ref, ProjectMaskAssetRef)

    def should_use_project_mask_color_channel(
        self,
        *,
        image_value: str,
        target: InputAssetStagingTarget,
        source_path: Path,
        workflow_name: str,
        workflow: object | None,
    ) -> bool:
        """Return whether a scalar staged mask is Substitute-authored grayscale."""

        if target.role.value != "mask":
            return False
        if self.is_project_mask(workflow=workflow, target=target):
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

    def _typed_scalar_source(
        self,
        *,
        target: InputAssetStagingTarget,
        workflow_name: str,
        workflow: object | None,
    ) -> InputAssetSourceResolution:
        """Resolve scalar typed metadata before applying legacy path heuristics."""

        if not isinstance(workflow, WorkflowState) or self._projects_dir is None:
            return InputAssetSourceResolution(False, None)
        assets = WorkflowAssetService()
        if target.role.value == "image":
            asset_ref = assets.input_image_asset_ref(
                workflow,
                section_key=target.section_key,
                node_name=target.node_name,
                field_key=target.field_key,
            )
            if asset_ref is None:
                return InputAssetSourceResolution(False, None)
            return InputAssetSourceResolution(
                True,
                assets.resolve_input_image_path(
                    workflow,
                    workflow_name=workflow_name,
                    section_key=target.section_key,
                    node_name=target.node_name,
                    field_key=target.field_key,
                    projects_dir=self._projects_dir,
                ),
            )
        asset_ref = assets.input_mask_asset_ref(
            workflow,
            section_key=target.section_key,
            node_name=target.node_name,
            field_key=target.field_key,
        )
        if asset_ref is None:
            return InputAssetSourceResolution(False, None)
        return InputAssetSourceResolution(
            True,
            assets.resolve_input_mask_path(
                workflow,
                workflow_name=workflow_name,
                section_key=target.section_key,
                node_name=target.node_name,
                field_key=target.field_key,
                projects_dir=self._projects_dir,
            ),
        )

    def _project_mask_path(self, workflow_name: str, relative_path: str) -> Path | None:
        """Resolve a project mask while rejecting traversal outside its owner."""

        if self._projects_dir is None:
            return None
        return _contained_project_path(
            self._projects_dir / workflow_name / "masks",
            relative_path,
        )


def _contained_project_path(root: Path, relative_path: str) -> Path | None:
    """Return a path only when it remains inside its resolved project root."""

    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        return None
    return candidate


def _looks_like_local_path(value: str) -> bool:
    """Return whether a graph value appears to reference a filesystem path."""

    path = Path(value)
    return (
        path.is_absolute()
        or PureWindowsPath(value).is_absolute()
        or PurePosixPath(value).is_absolute()
        or "\\" in value
    )


__all__ = [
    "InputAssetSourceResolution",
    "InputAssetSourceResolver",
    "OrderedInputAssetSource",
]
