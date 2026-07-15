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

"""Define durable workflow asset references owned by Substitute authoring state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, TypeAlias

from substitute.domain.common import JsonObject

WorkflowAssetKind: TypeAlias = Literal[
    "local_file",
    "project_asset",
    "project_mask",
    "comfy_input",
]


@dataclass(frozen=True)
class LocalFileAssetRef:
    """Reference a user-selected filesystem asset without copying it."""

    path: str
    kind: Literal["local_file"] = "local_file"

    def __post_init__(self) -> None:
        """Reject empty local file references."""

        if not self.path.strip():
            raise ValueError("Local file asset path must not be empty.")

    @classmethod
    def from_path(cls, path: Path | str) -> LocalFileAssetRef:
        """Build a local-file reference from a filesystem path."""

        return cls(path=str(Path(path)))


@dataclass(frozen=True)
class ProjectAssetRef:
    """Reference a durable Substitute-owned project asset."""

    relative_path: str
    kind: Literal["project_asset"] = "project_asset"

    def __post_init__(self) -> None:
        """Reject empty project asset references."""

        if not self.relative_path.strip():
            raise ValueError("Project asset path must not be empty.")


@dataclass(frozen=True)
class ProjectMaskAssetRef:
    """Reference a durable Substitute-owned project mask asset."""

    relative_path: str
    kind: Literal["project_mask"] = "project_mask"

    def __post_init__(self) -> None:
        """Reject empty project mask references."""

        if not self.relative_path.strip():
            raise ValueError("Project mask path must not be empty.")


@dataclass(frozen=True)
class ComfyInputAssetRef:
    """Reference an asset already known to Comfy's input namespace."""

    name: str
    kind: Literal["comfy_input"] = "comfy_input"

    def __post_init__(self) -> None:
        """Reject empty Comfy input references."""

        if not self.name.strip():
            raise ValueError("Comfy input asset name must not be empty.")


WorkflowAssetRef: TypeAlias = (
    LocalFileAssetRef | ProjectAssetRef | ProjectMaskAssetRef | ComfyInputAssetRef
)


def workflow_asset_ref_to_json(asset_ref: WorkflowAssetRef) -> JsonObject:
    """Serialize a workflow asset reference into persisted workflow metadata."""

    if isinstance(asset_ref, LocalFileAssetRef):
        return {"kind": asset_ref.kind, "path": asset_ref.path}
    if isinstance(asset_ref, ProjectAssetRef):
        return {"kind": asset_ref.kind, "relative_path": asset_ref.relative_path}
    if isinstance(asset_ref, ProjectMaskAssetRef):
        return {"kind": asset_ref.kind, "relative_path": asset_ref.relative_path}
    return {"kind": asset_ref.kind, "name": asset_ref.name}


def workflow_asset_ref_from_json(payload: Mapping[str, object]) -> WorkflowAssetRef:
    """Deserialize a workflow asset reference from persisted workflow metadata."""

    kind = payload.get("kind")
    if kind == "local_file":
        path = payload.get("path")
        if not isinstance(path, str):
            raise ValueError("Local file asset metadata is missing path.")
        return LocalFileAssetRef(path=path)
    if kind == "project_asset":
        relative_path = payload.get("relative_path")
        if not isinstance(relative_path, str):
            raise ValueError("Project asset metadata is missing relative_path.")
        return ProjectAssetRef(relative_path=relative_path)
    if kind == "project_mask":
        relative_path = payload.get("relative_path")
        if not isinstance(relative_path, str):
            raise ValueError("Project mask metadata is missing relative_path.")
        return ProjectMaskAssetRef(relative_path=relative_path)
    if kind == "comfy_input":
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Comfy input asset metadata is missing name.")
        return ComfyInputAssetRef(name=name)
    raise ValueError(f"Unknown workflow asset kind: {kind!r}")


def workflow_asset_ref_authoring_value(asset_ref: WorkflowAssetRef) -> str:
    """Return the graph-buffer value that represents an asset during authoring."""

    if isinstance(asset_ref, LocalFileAssetRef):
        return asset_ref.path
    if isinstance(asset_ref, ProjectAssetRef | ProjectMaskAssetRef):
        return asset_ref.relative_path
    return asset_ref.name


__all__ = [
    "ComfyInputAssetRef",
    "LocalFileAssetRef",
    "ProjectAssetRef",
    "ProjectMaskAssetRef",
    "WorkflowAssetKind",
    "WorkflowAssetRef",
    "workflow_asset_ref_authoring_value",
    "workflow_asset_ref_from_json",
    "workflow_asset_ref_to_json",
]
