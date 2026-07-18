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

"""Validate restore projection artifacts against workspace and backend identity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import math

from substitute.application.workspace_state.restore_projection_identity import (
    workspace_projection_fingerprint,
)
from substitute.application.workspace_state.restore_projection_codec import (
    restore_projection_artifact_to_json,
)
from substitute.application.workspace_state.restore_projection_models import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    RestoreProjectionArtifact,
)
from substitute.domain.workspace_snapshot import WorkspaceSnapshot

_QT_SLIDER_MAXIMUM = 2_147_483_647


class RestoreProjectionCacheState(StrEnum):
    """Describe the validation state for one projection artifact."""

    MISSING = "missing"
    UNREADABLE = "unreadable"
    SCHEMA_MISMATCH = "schema_mismatch"
    TARGET_MISMATCH = "target_mismatch"
    WORKSPACE_MISMATCH = "workspace_mismatch"
    BACKEND_PENDING = "backend_pending"
    VALID = "valid"
    STALE_CUBE = "stale_cube"
    STALE_NODE_DEFINITION = "stale_node_definition"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class RestoreProjectionInvalidation:
    """Describe one concrete cache validation mismatch."""

    state: RestoreProjectionCacheState
    reason: str
    cube_alias: str = ""
    node_class: str = ""


@dataclass(frozen=True, slots=True)
class RestoreProjectionValidationResult:
    """Return exact projection cache validation details."""

    state: RestoreProjectionCacheState
    reasons: tuple[str, ...] = ()
    stale_cube_aliases: tuple[str, ...] = ()
    stale_node_classes: tuple[str, ...] = ()
    invalidations: tuple[RestoreProjectionInvalidation, ...] = ()

    @property
    def can_build_provisionally(self) -> bool:
        """Return whether local identity permits provisional cache use."""

        return self.state in {
            RestoreProjectionCacheState.BACKEND_PENDING,
            RestoreProjectionCacheState.VALID,
        }

    @property
    def is_valid(self) -> bool:
        """Return whether live backend validation accepted the artifact."""

        return self.state is RestoreProjectionCacheState.VALID


class RestoreProjectionValidationService:
    """Validate projection artifacts before and after backend availability."""

    def validate_before_backend(
        self,
        artifact: RestoreProjectionArtifact,
        *,
        target_key: str,
        workspace: WorkspaceSnapshot,
    ) -> RestoreProjectionValidationResult:
        """Validate schema, target, safety, and durable workspace identity."""

        if artifact.schema_version != RESTORE_PROJECTION_CACHE_SCHEMA_VERSION:
            return _validation_result(
                RestoreProjectionCacheState.SCHEMA_MISMATCH,
                "Cache schema version is incompatible.",
            )
        if artifact.app_projection_version != APP_PROJECTION_VERSION:
            return _validation_result(
                RestoreProjectionCacheState.SCHEMA_MISMATCH,
                "App projection version is incompatible.",
            )
        unsafe_range_paths = _unsafe_slider_range_paths(
            restore_projection_artifact_to_json(artifact)
        )
        if unsafe_range_paths:
            return _validation_result(
                RestoreProjectionCacheState.INVALID,
                "Cache contains numeric slider metadata with a Qt-unsafe range: "
                f"{unsafe_range_paths[0]}.",
            )
        if artifact.target_key != target_key:
            return _validation_result(
                RestoreProjectionCacheState.TARGET_MISMATCH,
                "Cache target key does not match the active backend target.",
            )
        if artifact.workspace_fingerprint != workspace_projection_fingerprint(
            workspace
        ):
            return _validation_result(
                RestoreProjectionCacheState.WORKSPACE_MISMATCH,
                "Cache workspace fingerprint does not match the restored workspace.",
            )
        if artifact.active_route != workspace.active_route:
            return _validation_result(
                RestoreProjectionCacheState.WORKSPACE_MISMATCH,
                "Cache active route does not match the restored workspace.",
            )
        if artifact.active_workflow_id != workspace.active_workflow_id:
            return _validation_result(
                RestoreProjectionCacheState.WORKSPACE_MISMATCH,
                "Cache active workflow does not match the restored workspace.",
            )
        return _validation_result(
            RestoreProjectionCacheState.BACKEND_PENDING,
            "Cache matches local restore identity and awaits backend validation.",
        )

    def validate_after_backend(
        self,
        artifact: RestoreProjectionArtifact,
        *,
        live_cube_fingerprints: Mapping[str, str],
        live_node_fingerprints: Mapping[str, str],
    ) -> RestoreProjectionValidationResult:
        """Validate cached cube and node identities against the live backend."""

        stale_cubes = _stale_keys(
            artifact.cube_definition_fingerprints, live_cube_fingerprints
        )
        stale_nodes = _stale_keys(
            artifact.node_definition_fingerprints, live_node_fingerprints
        )
        invalidations = tuple(
            RestoreProjectionInvalidation(
                state=RestoreProjectionCacheState.STALE_CUBE,
                reason="Cached cube definition fingerprint differs from live data.",
                cube_alias=cube_alias,
            )
            for cube_alias in stale_cubes
        ) + tuple(
            RestoreProjectionInvalidation(
                state=RestoreProjectionCacheState.STALE_NODE_DEFINITION,
                reason="Cached node definition fingerprint differs from live data.",
                node_class=node_class,
            )
            for node_class in stale_nodes
        )
        if stale_cubes:
            return RestoreProjectionValidationResult(
                state=RestoreProjectionCacheState.STALE_CUBE,
                reasons=tuple(item.reason for item in invalidations),
                stale_cube_aliases=tuple(stale_cubes),
                stale_node_classes=tuple(stale_nodes),
                invalidations=invalidations,
            )
        if stale_nodes:
            return RestoreProjectionValidationResult(
                state=RestoreProjectionCacheState.STALE_NODE_DEFINITION,
                reasons=tuple(item.reason for item in invalidations),
                stale_node_classes=tuple(stale_nodes),
                invalidations=invalidations,
            )
        return _validation_result(
            RestoreProjectionCacheState.VALID,
            "Cached projection identities match live backend data.",
        )


def _validation_result(
    state: RestoreProjectionCacheState, reason: str
) -> RestoreProjectionValidationResult:
    """Build one single-reason validation result."""

    return RestoreProjectionValidationResult(state=state, reasons=(reason,))


def _stale_keys(cached: Mapping[str, str], live: Mapping[str, str]) -> list[str]:
    """Return sorted cached keys absent from or changed in live identities."""

    return sorted(
        key for key, fingerprint in cached.items() if live.get(key) != fingerprint
    )


def _unsafe_slider_range_paths(value: object) -> tuple[str, ...]:
    """Return cache paths containing unsafe integer slider ranges."""

    paths: list[str] = []
    _collect_unsafe_slider_range_paths(value, path="$", paths=paths)
    return tuple(paths)


def _collect_unsafe_slider_range_paths(
    value: object, *, path: str, paths: list[str]
) -> None:
    """Collect unsafe range paths recursively."""

    if isinstance(value, Mapping):
        if _mapping_has_unsafe_slider_range(value):
            paths.append(path)
        for key, item in value.items():
            _collect_unsafe_slider_range_paths(item, path=f"{path}.{key}", paths=paths)
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _collect_unsafe_slider_range_paths(
                item, path=f"{path}[{index}]", paths=paths
            )


def _mapping_has_unsafe_slider_range(value: Mapping[object, object]) -> bool:
    """Return whether a mapping describes a Qt-unsafe integer slider range."""

    minimum = _float_or_none(value.get("min"))
    maximum = _float_or_none(value.get("max"))
    if minimum is None and maximum is None:
        return False
    numeric_kind = str(value.get("field_type", value.get("type", ""))).casefold()
    if numeric_kind and not any(
        token in numeric_kind for token in ("int", "number", "seed")
    ):
        return False
    return bool(
        minimum is not None
        and minimum < -_QT_SLIDER_MAXIMUM
        or maximum is not None
        and maximum > _QT_SLIDER_MAXIMUM
    )


def _float_or_none(value: object) -> float | None:
    """Return a finite numeric value as float."""

    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


__all__ = [
    "RestoreProjectionCacheState",
    "RestoreProjectionInvalidation",
    "RestoreProjectionValidationResult",
    "RestoreProjectionValidationService",
]
