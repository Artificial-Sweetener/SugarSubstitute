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

"""Detect loaded workflow cubes that have newer Cube Library versions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from substitute.domain.cube_library import (
    CubeCatalog,
    CubeUpdatePolicy,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info

_LOGGER = get_logger("application.cube_library.update_detection")


class CubeLibraryUpdateReason(StrEnum):
    """Describe why a loaded Cube Library cube can be updated."""

    VERSION_DRIFT = "version_drift"


class LoadedCubeUpdateAction(StrEnum):
    """Describe one user-selected action for a stale loaded cube instance."""

    KEEP_PINNED = "keep_pinned"
    UPDATE_INSTANCE = "update_instance"
    UPDATE_MATCHING_VERSION = "update_matching_version"
    SWITCH_TO_VERSION = "switch_to_version"
    FOLLOW_LATEST = "follow_latest"


class LoadedCubeStateProtocol(Protocol):
    """Describe loaded cube state needed for version drift detection."""

    cube_id: str
    version: str
    alias: str
    display_name: str
    ui: dict[str, object] | None
    update_policy: CubeUpdatePolicy


class WorkflowStateProtocol(Protocol):
    """Describe workflow state scanned by update detection."""

    cubes: Mapping[str, LoadedCubeStateProtocol]


@dataclass(frozen=True, slots=True)
class LoadedCubeUpdateCandidate:
    """Represent one loaded cube that can be refreshed to a newer version."""

    workflow_id: str
    workflow_name: str
    cube_alias: str
    cube_id: str
    current_version: str
    latest_version: str
    catalog_revision: str
    display_name: str
    reason: CubeLibraryUpdateReason
    update_policy: CubeUpdatePolicy = CubeUpdatePolicy.PINNED


@dataclass(frozen=True, slots=True)
class LoadedCubeUpdateSelection:
    """Represent the user's action for one update candidate row."""

    candidate: LoadedCubeUpdateCandidate
    action: LoadedCubeUpdateAction
    target_version: str | None = None


@dataclass(frozen=True, slots=True)
class LoadedCubeUpdateGroup:
    """Represent update candidates that share the same current cube version."""

    cube_id: str
    current_version: str
    candidates: tuple[LoadedCubeUpdateCandidate, ...]


class CubeLibraryUpdateDetectionService:
    """Compare loaded workflow cubes with the latest Cube Library catalog."""

    def detect_updates(
        self,
        *,
        workflows: Mapping[str, object],
        workflow_names: Mapping[str, str],
        catalog: CubeCatalog,
    ) -> tuple[LoadedCubeUpdateCandidate, ...]:
        """Return loaded cubes whose semantic version differs from the catalog."""

        catalog_by_cube_id = {entry.cube_id: entry for entry in catalog.cubes}
        candidates: list[LoadedCubeUpdateCandidate] = []
        loaded_cube_count = 0
        for workflow_id, workflow in workflows.items():
            cubes = getattr(workflow, "cubes", None)
            if not isinstance(cubes, Mapping):
                continue
            workflow_name = workflow_names.get(workflow_id, workflow_id)
            for cube_alias, cube_state in cubes.items():
                loaded_cube_count += 1
                cube_id = _read_text(getattr(cube_state, "cube_id", ""))
                if not cube_id:
                    continue
                catalog_entry = catalog_by_cube_id.get(cube_id)
                if catalog_entry is None:
                    continue
                current_version = _read_text(getattr(cube_state, "version", ""))
                latest_version = catalog_entry.version.strip()
                reason = _update_reason(
                    current_version=current_version,
                    latest_version=latest_version,
                )
                if reason is None:
                    continue
                candidate = LoadedCubeUpdateCandidate(
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    cube_alias=str(cube_alias),
                    cube_id=cube_id,
                    current_version=current_version,
                    latest_version=latest_version,
                    catalog_revision=catalog.catalog_revision,
                    display_name=catalog_entry.display_name
                    or _read_text(getattr(cube_state, "display_name", "")),
                    reason=reason,
                    update_policy=_loaded_update_policy(cube_state),
                )
                candidates.append(candidate)
                log_debug(
                    _LOGGER,
                    "Detected loaded Cube Library update candidate",
                    workflow_id=workflow_id,
                    cube_alias=str(cube_alias),
                    cube_id=cube_id,
                    current_version=current_version,
                    latest_version=latest_version,
                    reason=reason.value,
                )
        log_info(
            _LOGGER,
            "Scanned loaded cubes for Cube Library version drift",
            loaded_cube_count=loaded_cube_count,
            stale_cube_count=len(candidates),
            catalog_revision=catalog.catalog_revision,
        )
        return tuple(candidates)


def group_loaded_cube_update_candidates_by_current_version(
    candidates: Sequence[LoadedCubeUpdateCandidate],
) -> tuple[LoadedCubeUpdateGroup, ...]:
    """Group candidates that can be updated together by current cube version."""

    groups: dict[tuple[str, str], list[LoadedCubeUpdateCandidate]] = {}
    for candidate in candidates:
        if not candidate.cube_id or not candidate.current_version:
            continue
        groups.setdefault((candidate.cube_id, candidate.current_version), []).append(
            candidate
        )
    return tuple(
        LoadedCubeUpdateGroup(
            cube_id=cube_id,
            current_version=current_version,
            candidates=tuple(group),
        )
        for (cube_id, current_version), group in groups.items()
    )


def _loaded_update_policy(cube_state: object) -> CubeUpdatePolicy:
    """Return the update policy stored on a workflow cube instance."""

    update_policy = getattr(cube_state, "update_policy", None)
    if isinstance(update_policy, CubeUpdatePolicy):
        return update_policy
    return CubeUpdatePolicy.PINNED


def _read_text(value: object) -> str:
    """Return one stripped string value."""

    return value.strip() if isinstance(value, str) else ""


def _update_reason(
    *,
    current_version: str,
    latest_version: str,
) -> CubeLibraryUpdateReason | None:
    """Return the update reason for version drift only."""

    if not latest_version:
        return None
    if current_version != latest_version:
        return CubeLibraryUpdateReason.VERSION_DRIFT
    return None


__all__ = [
    "CubeLibraryUpdateDetectionService",
    "CubeLibraryUpdateReason",
    "LoadedCubeUpdateAction",
    "LoadedCubeUpdateCandidate",
    "LoadedCubeUpdateGroup",
    "LoadedCubeUpdateSelection",
    "group_loaded_cube_update_candidates_by_current_version",
]
