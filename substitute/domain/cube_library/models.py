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

"""Represent target-owned Cube Library data without Qt dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.common import JsonObject


@dataclass(frozen=True, slots=True)
class CubeVersionIdentity:
    """Identify the cube version selected by one workflow instance."""

    cube_id: str
    version: str

    def to_payload(self) -> JsonObject:
        """Return the persisted public payload for this version identity."""

        return {
            "cubeId": self.cube_id,
            "version": self.version,
        }


class CubeUpdatePolicy(StrEnum):
    """Describe how a workflow cube instance follows library changes."""

    PINNED = "pinned"
    FOLLOW_LATEST = "follow_latest"


@dataclass(frozen=True)
class CubeSourceMetadata:
    """Describe where a cube artifact came from on the active target."""

    kind: str
    path: str
    repo_ref: str = ""
    owner: str = ""
    repo: str = ""
    branch: str = ""
    namespace: str = ""
    local_head_sha: str = ""
    remote_head_sha: str = ""
    dirty: bool = False


@dataclass(frozen=True)
class CubeIconDescriptor:
    """Describe a Cube Library icon asset without presentation dependencies."""

    kind: str
    url: str = ""
    media_type: str = ""
    repo_relative_path: str = ""
    color_behavior: str = "auto"


@dataclass(frozen=True)
class CubeCatalogEntry:
    """Represent one selectable cube from a target catalog."""

    cube_id: str
    version: str
    display_name: str
    description: str
    source: CubeSourceMetadata
    content_hash: str
    updated_at: str = ""
    supported_models: tuple[str, ...] = ()
    icon: CubeIconDescriptor | None = None


@dataclass(frozen=True)
class CubeCatalog:
    """Represent a complete Cube Library catalog snapshot."""

    schema_version: int
    catalog_revision: str
    generated_at: str
    cubes: tuple[CubeCatalogEntry, ...]


@dataclass(frozen=True)
class LoadedCubeArtifact:
    """Represent a loaded target cube artifact and its diagnostics metadata."""

    cube_id: str
    version: str
    display_name: str
    content_hash: str
    source: CubeSourceMetadata
    cube: JsonObject
    icon: CubeIconDescriptor | None = None


@dataclass(frozen=True)
class CubeLibraryStatus:
    """Represent active target Cube Library availability."""

    schema_version: int
    available: bool
    source: str
    catalog_revision: str
    pack_management_supported: bool
    local_authoring_supported: bool
    readiness_supported: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CubePackRecord:
    """Represent one tracked Cube Pack on the active target."""

    repo_ref: str
    owner: str
    repo: str
    branch: str
    enabled: bool
    default_base_repo: bool
    auto_update: bool
    local_head_sha: str
    remote_head_sha: str
    update_available: bool
    last_sync_at: str
    last_sync_status: str
    last_sync_error: str
    last_checked_at: str
    last_check_status: str
    last_check_error: str
    cube_count: int


@dataclass(frozen=True)
class CubePackPreflight:
    """Represent preflight results for a candidate Cube Pack."""

    owner: str
    repo: str
    branch: str
    contains_cubes: bool
    cube_count: int
    cube_paths: tuple[str, ...]
    truncated: bool
    checked_via: str


@dataclass(frozen=True)
class CubeLibraryReadiness:
    """Represent target dependency readiness for the active Cube Library."""

    schema_version: int
    ready: bool
    required_custom_nodes: tuple[str, ...]
    missing_custom_nodes: tuple[str, ...]
    installed_custom_nodes: tuple[str, ...]
    can_install: bool
    install_supported: bool
    catalog_revision: str
    errors: tuple[str, ...]
    install_plan: tuple["CubeDependencyInstallPlanItem", ...] = ()
    restart_required: bool = False
    versioned_requirements_supported: bool = False
    dependency_version_plan: tuple["CubeDependencyVersionPlanItem", ...] = ()
    comfy_runtime: "CubeRuntimeReadiness | None" = None


@dataclass(frozen=True)
class CubeDependencyInstallPlanItem:
    """Represent one installable or blocked custom-node dependency."""

    node_id: str
    display_name: str
    existing_folder_name: str
    required_by_packs: tuple[str, ...]
    required_by_cube_ids: tuple[str, ...]
    default_base_only: bool
    confirmation_required: bool
    installable: bool
    installed: bool
    remediation: str


@dataclass(frozen=True)
class CubeDependencyVersionPlanItem:
    """Represent version readiness for one required custom-node dependency."""

    node_id: str
    display_name: str
    required_version: str
    required_version_kind: str
    installed_version: str
    installed_version_kind: str
    status: str
    repairable: bool
    restart_required_after_repair: bool
    required_by_packs: tuple[str, ...]
    required_by_cube_ids: tuple[str, ...]
    required_by_nodes: tuple[str, ...]
    remediation: str


@dataclass(frozen=True)
class CubeRuntimeReadiness:
    """Represent Comfy runtime requirements declared by enabled cubes."""

    schema_version: int
    required_version: str
    required_version_kind: str
    installed_version: str
    status: str
    remediation: str = ""


@dataclass(frozen=True)
class CubeDependencyRepairRequest:
    """Describe an approved dependency repair request."""

    baseline_only: bool = False
    approved_node_ids: tuple[str, ...] = ()
    sync_enabled_repos: bool = False

    def to_payload(self) -> JsonObject:
        """Return the backend repair request payload."""

        return {
            "baselineOnly": self.baseline_only,
            "approvedNodeIds": list(self.approved_node_ids),
            "syncEnabledRepos": self.sync_enabled_repos,
        }


@dataclass(frozen=True)
class CubeDependencyRepairResult:
    """Represent the result of dependency repair on the active target."""

    schema_version: int
    readiness_before: CubeLibraryReadiness
    attempted_install_plan: tuple[CubeDependencyInstallPlanItem, ...]
    installed_nodes: tuple[str, ...]
    skipped_nodes: tuple[str, ...]
    failed_nodes: tuple[str, ...]
    readiness_after: CubeLibraryReadiness
    restart_required: bool


@dataclass(frozen=True)
class CubeDependencySyncAndCheckRequest:
    """Describe shared Cube Pack sync and dependency readiness orchestration."""

    sync_mode: str = ""
    owner: str = ""
    repo: str = ""
    include_versions: bool = True
    baseline_only: bool = False
    approved_node_ids: tuple[str, ...] = ()
    repair: bool = False

    def to_payload(self) -> JsonObject:
        """Return the backend sync-and-check request payload."""

        return {
            "sync": {
                "mode": self.sync_mode,
                "owner": self.owner,
                "repo": self.repo,
            },
            "dependencyPolicy": {
                "includeVersions": self.include_versions,
                "baselineOnly": self.baseline_only,
                "approvedNodeIds": list(self.approved_node_ids),
                "repair": self.repair,
            },
        }


@dataclass(frozen=True)
class CubeDependencySyncAndCheckResult:
    """Represent shared sync, dependency planning, repair, and restart facts."""

    schema_version: int
    readiness: CubeLibraryReadiness
    repair_result: CubeDependencyRepairResult | None
    restart_required: bool
    errors: tuple[str, ...]
