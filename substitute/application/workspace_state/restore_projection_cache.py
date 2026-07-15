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

"""Model and validate durable restored editor projection cache artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import math
from typing import Protocol

from substitute.application.cubes import LoadedCubeDefinition
from substitute.domain.common import JsonObject
from substitute.domain.prompt import PromptEditorFeatureProfile
from substitute.domain.workspace_snapshot import WorkspaceSnapshot

RESTORE_PROJECTION_CACHE_SCHEMA_VERSION = 1
APP_PROJECTION_VERSION = 2
_QT_SLIDER_MAXIMUM = 2_147_483_647


class RestoreProjectionCacheState(StrEnum):
    """Describe the validation state for one restore projection cache artifact."""

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
class RestoreProjectionCacheKey:
    """Identify the backend target and workspace a cache artifact belongs to."""

    target_key: str
    workspace_fingerprint: str


@dataclass(frozen=True, slots=True)
class CachedNodeProjection:
    """Store resolved node projection data without any Qt object state."""

    node_name: str
    node_class: str
    field_order: tuple[str, ...] = ()
    resolved_field_specs: JsonObject = field(default_factory=dict)
    resolved_card_visibility: JsonObject = field(default_factory=dict)
    prompt_field_metadata: JsonObject = field(default_factory=dict)

    def to_json(self) -> JsonObject:
        """Serialize this node projection to a JSON-compatible mapping."""

        return {
            "node_name": self.node_name,
            "node_class": self.node_class,
            "field_order": list(self.field_order),
            "resolved_field_specs": self.resolved_field_specs,
            "resolved_card_visibility": self.resolved_card_visibility,
            "prompt_field_metadata": self.prompt_field_metadata,
        }

    @classmethod
    def from_json(cls, value: object) -> CachedNodeProjection:
        """Deserialize one cached node projection or raise `ValueError`."""

        payload = _mapping(value, "cached node projection")
        return cls(
            node_name=_required_str(payload, "node_name"),
            node_class=_required_str(payload, "node_class"),
            field_order=_str_tuple(payload.get("field_order"), "field_order"),
            resolved_field_specs=_json_object(
                payload.get("resolved_field_specs"),
                "resolved_field_specs",
            ),
            resolved_card_visibility=_json_object(
                payload.get("resolved_card_visibility"),
                "resolved_card_visibility",
            ),
            prompt_field_metadata=_json_object(
                payload.get("prompt_field_metadata"),
                "prompt_field_metadata",
            ),
        )


@dataclass(frozen=True, slots=True)
class CachedCubeProjection:
    """Store one cube-section projection identity and resolved rendering data."""

    alias: str
    requested_cube_id: str
    canonical_cube_id: str
    cube_version: str
    content_hash: str
    catalog_revision: str
    buffer_fingerprint: str
    node_classes: tuple[str, ...]
    node_definition_fingerprint_by_class: Mapping[str, str]
    projected_node_order: tuple[str, ...]
    resolved_field_specs: JsonObject = field(default_factory=dict)
    resolved_card_visibility: JsonObject = field(default_factory=dict)
    field_order: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    prompt_field_metadata: JsonObject = field(default_factory=dict)
    nodes: tuple[CachedNodeProjection, ...] = ()

    def to_json(self) -> JsonObject:
        """Serialize this cube projection to a JSON-compatible mapping."""

        return {
            "alias": self.alias,
            "requested_cube_id": self.requested_cube_id,
            "canonical_cube_id": self.canonical_cube_id,
            "cube_version": self.cube_version,
            "content_hash": self.content_hash,
            "catalog_revision": self.catalog_revision,
            "buffer_fingerprint": self.buffer_fingerprint,
            "node_classes": list(self.node_classes),
            "node_definition_fingerprint_by_class": dict(
                self.node_definition_fingerprint_by_class
            ),
            "projected_node_order": list(self.projected_node_order),
            "resolved_field_specs": self.resolved_field_specs,
            "resolved_card_visibility": self.resolved_card_visibility,
            "field_order": {
                node_name: list(fields)
                for node_name, fields in self.field_order.items()
            },
            "prompt_field_metadata": self.prompt_field_metadata,
            "nodes": [node.to_json() for node in self.nodes],
        }

    @classmethod
    def from_json(cls, value: object) -> CachedCubeProjection:
        """Deserialize one cached cube projection or raise `ValueError`."""

        payload = _mapping(value, "cached cube projection")
        return cls(
            alias=_required_str(payload, "alias"),
            requested_cube_id=_required_str(payload, "requested_cube_id"),
            canonical_cube_id=_required_str(payload, "canonical_cube_id"),
            cube_version=_required_str(payload, "cube_version"),
            content_hash=_required_str(payload, "content_hash"),
            catalog_revision=_required_str(payload, "catalog_revision"),
            buffer_fingerprint=_required_str(payload, "buffer_fingerprint"),
            node_classes=_str_tuple(payload.get("node_classes"), "node_classes"),
            node_definition_fingerprint_by_class=_str_mapping(
                payload.get("node_definition_fingerprint_by_class"),
                "node_definition_fingerprint_by_class",
            ),
            projected_node_order=_str_tuple(
                payload.get("projected_node_order"),
                "projected_node_order",
            ),
            resolved_field_specs=_json_object(
                payload.get("resolved_field_specs"),
                "resolved_field_specs",
            ),
            resolved_card_visibility=_json_object(
                payload.get("resolved_card_visibility"),
                "resolved_card_visibility",
            ),
            field_order={
                str(node_name): _str_tuple(fields, f"field_order[{node_name}]")
                for node_name, fields in _mapping(
                    payload.get("field_order", {}),
                    "field_order",
                ).items()
            },
            prompt_field_metadata=_json_object(
                payload.get("prompt_field_metadata"),
                "prompt_field_metadata",
            ),
            nodes=tuple(
                CachedNodeProjection.from_json(node)
                for node in _sequence(payload.get("nodes", ()), "nodes")
            ),
        )


@dataclass(frozen=True, slots=True)
class CachedWorkflowProjection:
    """Store projection data for one restored workflow tab."""

    workflow_id: str
    tab_label: str
    stack_order: tuple[str, ...]
    active_cube_alias: str | None
    cube_aliases: tuple[str, ...]
    workflow_fingerprint: str
    cubes: tuple[CachedCubeProjection, ...] = ()

    def to_json(self) -> JsonObject:
        """Serialize this workflow projection to a JSON-compatible mapping."""

        return {
            "workflow_id": self.workflow_id,
            "tab_label": self.tab_label,
            "stack_order": list(self.stack_order),
            "active_cube_alias": self.active_cube_alias,
            "cube_aliases": list(self.cube_aliases),
            "workflow_fingerprint": self.workflow_fingerprint,
            "cubes": [cube.to_json() for cube in self.cubes],
        }

    @classmethod
    def from_json(cls, value: object) -> CachedWorkflowProjection:
        """Deserialize one cached workflow projection or raise `ValueError`."""

        payload = _mapping(value, "cached workflow projection")
        active_alias = payload.get("active_cube_alias")
        if active_alias is not None and not isinstance(active_alias, str):
            raise ValueError("active_cube_alias must be a string or null.")
        return cls(
            workflow_id=_required_str(payload, "workflow_id"),
            tab_label=_required_str(payload, "tab_label"),
            stack_order=_str_tuple(payload.get("stack_order"), "stack_order"),
            active_cube_alias=active_alias,
            cube_aliases=_str_tuple(payload.get("cube_aliases"), "cube_aliases"),
            workflow_fingerprint=_required_str(payload, "workflow_fingerprint"),
            cubes=tuple(
                CachedCubeProjection.from_json(cube)
                for cube in _sequence(payload.get("cubes", ()), "cubes")
            ),
        )


@dataclass(frozen=True, slots=True)
class RestoreProjectionArtifact:
    """Store one last-known-good restored editor projection cache artifact."""

    schema_version: int
    created_at: str
    app_projection_version: int
    target_key: str
    workspace_fingerprint: str
    active_route: str
    active_workflow_id: str
    workflows: tuple[CachedWorkflowProjection, ...]
    prompt_editor_feature_profile_fingerprint: str
    node_definition_fingerprints: Mapping[str, str]
    cube_definition_fingerprints: Mapping[str, str]
    projection: JsonObject = field(default_factory=dict)

    def to_json(self) -> JsonObject:
        """Serialize this artifact to the durable cache JSON shape."""

        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "app_projection_version": self.app_projection_version,
            "target_key": self.target_key,
            "workspace_fingerprint": self.workspace_fingerprint,
            "active_route": self.active_route,
            "active_workflow_id": self.active_workflow_id,
            "workflows": [workflow.to_json() for workflow in self.workflows],
            "prompt_editor_feature_profile_fingerprint": (
                self.prompt_editor_feature_profile_fingerprint
            ),
            "node_definition_fingerprints": dict(self.node_definition_fingerprints),
            "cube_definition_fingerprints": dict(self.cube_definition_fingerprints),
            "projection": self.projection,
        }

    @classmethod
    def from_json(cls, value: object) -> RestoreProjectionArtifact:
        """Deserialize one restore projection artifact or raise `ValueError`."""

        payload = _mapping(value, "restore projection artifact")
        schema_version = _required_int(payload, "schema_version")
        app_projection_version = _required_int(payload, "app_projection_version")
        if schema_version != RESTORE_PROJECTION_CACHE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported restore projection cache schema_version {schema_version}."
            )
        if app_projection_version != APP_PROJECTION_VERSION:
            raise ValueError(
                "Unsupported restore projection app_projection_version "
                f"{app_projection_version}."
            )
        return cls(
            schema_version=schema_version,
            created_at=_required_str(payload, "created_at"),
            app_projection_version=app_projection_version,
            target_key=_required_str(payload, "target_key"),
            workspace_fingerprint=_required_str(payload, "workspace_fingerprint"),
            active_route=_required_str(payload, "active_route"),
            active_workflow_id=_required_str(payload, "active_workflow_id"),
            workflows=tuple(
                CachedWorkflowProjection.from_json(workflow)
                for workflow in _sequence(payload.get("workflows"), "workflows")
            ),
            prompt_editor_feature_profile_fingerprint=_required_str(
                payload,
                "prompt_editor_feature_profile_fingerprint",
            ),
            node_definition_fingerprints=_str_mapping(
                payload.get("node_definition_fingerprints"),
                "node_definition_fingerprints",
            ),
            cube_definition_fingerprints=_str_mapping(
                payload.get("cube_definition_fingerprints"),
                "cube_definition_fingerprints",
            ),
            projection=_json_object(payload.get("projection"), "projection"),
        )


@dataclass(frozen=True, slots=True)
class RestoreProjectionInvalidation:
    """Describe one concrete validation mismatch."""

    state: RestoreProjectionCacheState
    reason: str
    cube_alias: str = ""
    node_class: str = ""


@dataclass(frozen=True, slots=True)
class RestoreProjectionValidationResult:
    """Return exact restore projection cache validation outcome details."""

    state: RestoreProjectionCacheState
    reasons: tuple[str, ...] = ()
    stale_cube_aliases: tuple[str, ...] = ()
    stale_node_classes: tuple[str, ...] = ()
    invalidations: tuple[RestoreProjectionInvalidation, ...] = ()

    @property
    def can_build_provisionally(self) -> bool:
        """Return whether cached projection can be built before backend readiness."""

        return self.state in {
            RestoreProjectionCacheState.BACKEND_PENDING,
            RestoreProjectionCacheState.VALID,
        }

    @property
    def is_valid(self) -> bool:
        """Return whether live backend validation accepted the artifact."""

        return self.state is RestoreProjectionCacheState.VALID


class RestoreProjectionCacheRepository(Protocol):
    """Persist and load restore projection cache artifacts."""

    def load(self) -> RestoreProjectionArtifact | None:
        """Return the latest cache artifact when readable."""

    def save(self, artifact: RestoreProjectionArtifact) -> None:
        """Persist one cache artifact atomically."""

    def clear(self) -> None:
        """Remove invalid or obsolete cache state."""


class RestoreProjectionValidationService:
    """Validate provisional restore projections against workspace and backend data."""

    def validate_before_backend(
        self,
        artifact: RestoreProjectionArtifact,
        *,
        target_key: str,
        workspace: WorkspaceSnapshot,
    ) -> RestoreProjectionValidationResult:
        """Return whether an artifact can be built provisionally."""

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
        unsafe_range_paths = _unsafe_slider_range_paths(artifact.to_json())
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
        expected_workspace_fingerprint = workspace_projection_fingerprint(workspace)
        if artifact.workspace_fingerprint != expected_workspace_fingerprint:
            if not (
                _matches_legacy_override_selection_fingerprint(artifact, workspace)
                or _matches_legacy_active_cube_alias_fingerprint(
                    artifact,
                    workspace,
                )
                or _matches_legacy_cube_source_identity_fingerprint(
                    artifact,
                    workspace,
                )
            ):
                return _validation_result(
                    RestoreProjectionCacheState.WORKSPACE_MISMATCH,
                    "Cache workspace fingerprint does not match the restored workspace.",
                )
            legacy_fingerprint_accepted = True
        else:
            legacy_fingerprint_accepted = False
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
            (
                "Cache matches local restore identity after ignoring cube focus drift."
                if legacy_fingerprint_accepted
                else "Cache matches local restore identity and awaits backend validation."
            ),
        )

    def validate_after_backend(
        self,
        artifact: RestoreProjectionArtifact,
        *,
        live_cube_fingerprints: Mapping[str, str],
        live_node_fingerprints: Mapping[str, str],
    ) -> RestoreProjectionValidationResult:
        """Return whether live backend identities match the cached projection."""

        stale_cubes = _stale_keys(
            artifact.cube_definition_fingerprints,
            live_cube_fingerprints,
        )
        stale_nodes = _stale_keys(
            artifact.node_definition_fingerprints,
            live_node_fingerprints,
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
                reasons=tuple(invalidation.reason for invalidation in invalidations),
                stale_cube_aliases=tuple(stale_cubes),
                stale_node_classes=tuple(stale_nodes),
                invalidations=invalidations,
            )
        if stale_nodes:
            return RestoreProjectionValidationResult(
                state=RestoreProjectionCacheState.STALE_NODE_DEFINITION,
                reasons=tuple(invalidation.reason for invalidation in invalidations),
                stale_node_classes=tuple(stale_nodes),
                invalidations=invalidations,
            )
        return _validation_result(
            RestoreProjectionCacheState.VALID,
            "Cached projection identities match live backend data.",
        )


def fingerprint_json(value: object) -> str:
    """Return a deterministic SHA-256 fingerprint for JSON-compatible data."""

    encoded = json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def workspace_projection_fingerprint(snapshot: WorkspaceSnapshot) -> str:
    """Return the structural restore-projection identity for a workspace."""

    return _workspace_projection_fingerprint(
        snapshot,
        active_cube_alias_by_workflow=None,
    )


def _workspace_projection_fingerprint(
    snapshot: WorkspaceSnapshot,
    *,
    active_cube_alias_by_workflow: Mapping[str, str | None] | None,
    include_override_selections: bool = True,
    include_cube_source_identity: bool = True,
    include_cube_bypass_state: bool = True,
) -> str:
    """Return a workspace fingerprint with optional legacy cube focus state."""

    workflows_by_id = {
        workflow.workflow_id: workflow for workflow in snapshot.workflows
    }
    workflow_order = snapshot.tab_order or tuple(workflows_by_id)
    workflows: list[JsonObject] = []
    for workflow_id in workflow_order:
        workflow = workflows_by_id.get(workflow_id)
        if workflow is None:
            continue
        state = workflow.workflow
        cubes: list[JsonObject] = []
        for alias in state.stack_order:
            cube = state.cubes.get(alias)
            if cube is None:
                continue
            cube_identity: JsonObject = {
                "alias": alias,
                "cube_id": cube.cube_id,
                "version": cube.version,
                "display_name": cube.display_name,
                "buffer_fingerprint": fingerprint_json(cube.buffer),
            }
            if include_cube_bypass_state:
                cube_identity["bypassed"] = cube.bypassed
            if include_cube_source_identity:
                cube_identity["content_hash"] = _cube_ui_text(cube, "content_hash")
                cube_identity["catalog_revision"] = _cube_ui_text(
                    cube,
                    "catalog_revision",
                )
            cubes.append(cube_identity)
        workflow_identity: JsonObject = {
            "workflow_id": workflow.workflow_id,
            "tab_label": workflow.tab_label,
            "stack_order": list(state.stack_order),
            "global_overrides": state.global_overrides,
            "cubes": cubes,
        }
        if include_override_selections:
            workflow_identity["global_override_selections"] = (
                state.global_override_selections
            )
        if active_cube_alias_by_workflow is not None:
            workflow_identity["active_cube_alias"] = active_cube_alias_by_workflow.get(
                workflow.workflow_id,
                workflow.active_cube_alias,
            )
        workflows.append(workflow_identity)
    return fingerprint_json(
        {
            "schema_version": snapshot.schema_version,
            "active_route": snapshot.active_route,
            "active_workflow_id": snapshot.active_workflow_id,
            "tab_order": list(snapshot.tab_order),
            "workflows": workflows,
        }
    )


def _matches_legacy_override_selection_fingerprint(
    artifact: RestoreProjectionArtifact,
    workspace: WorkspaceSnapshot,
) -> bool:
    """Return whether a cache matches identity before selections were persisted."""

    return artifact.workspace_fingerprint == _workspace_projection_fingerprint(
        workspace,
        active_cube_alias_by_workflow=None,
        include_override_selections=False,
        include_cube_source_identity=False,
        include_cube_bypass_state=False,
    )


def _matches_legacy_active_cube_alias_fingerprint(
    artifact: RestoreProjectionArtifact,
    workspace: WorkspaceSnapshot,
) -> bool:
    """Return whether a cache matches the old cube-focus-sensitive fingerprint."""

    active_aliases = {
        workflow.workflow_id: workflow.active_cube_alias
        for workflow in artifact.workflows
    }
    if not active_aliases:
        return False
    return artifact.workspace_fingerprint == _workspace_projection_fingerprint(
        workspace,
        active_cube_alias_by_workflow=active_aliases,
        include_override_selections=False,
        include_cube_source_identity=False,
        include_cube_bypass_state=False,
    )


def _matches_legacy_cube_source_identity_fingerprint(
    artifact: RestoreProjectionArtifact,
    workspace: WorkspaceSnapshot,
) -> bool:
    """Return whether a cache matches identity before cube source fields were added."""

    return artifact.workspace_fingerprint == _workspace_projection_fingerprint(
        workspace,
        active_cube_alias_by_workflow=None,
        include_cube_source_identity=False,
        include_cube_bypass_state=False,
    )


def cube_definition_fingerprint(definition: LoadedCubeDefinition) -> str:
    """Return a stable fingerprint for one live loaded cube definition."""

    ui_payload = (
        definition.ui_payload if isinstance(definition.ui_payload, dict) else {}
    )
    canonical_cube = ui_payload.get("canonical_cube")
    safe_ui_payload = {
        "catalog_revision": ui_payload.get("catalog_revision"),
        "content_hash": ui_payload.get("content_hash"),
        "canonical_cube": canonical_cube if isinstance(canonical_cube, dict) else {},
        "schema_version": ui_payload.get("schema_version"),
        "artifact_label": ui_payload.get("artifact_label"),
    }
    return fingerprint_json(
        {
            "cube_id": definition.cube_id,
            "version": definition.version,
            "display_name": definition.display_name,
            "graph": definition.graph,
            "ui_payload": safe_ui_payload,
        }
    )


def _cube_ui_text(cube: object, key: str) -> str:
    """Return one string value from cube UI metadata."""

    ui_payload = getattr(cube, "ui", None)
    if not isinstance(ui_payload, Mapping):
        return ""
    value = ui_payload.get(key)
    return value if isinstance(value, str) else ""


def node_definition_fingerprint(payload: Mapping[str, object]) -> str:
    """Return a stable fingerprint for one Comfy node definition payload."""

    return fingerprint_json(dict(payload))


def prompt_feature_profile_fingerprint(
    profile: PromptEditorFeatureProfile,
) -> str:
    """Return a stable fingerprint for prompt editor rendering capabilities."""

    return fingerprint_json(
        {
            "decisions": [
                {
                    "feature": decision.feature.value,
                    "enabled": decision.enabled,
                    "disabled_reason": (
                        decision.disabled_reason.value
                        if decision.disabled_reason is not None
                        else None
                    ),
                    "detail": decision.detail,
                }
                for decision in sorted(
                    profile.decisions,
                    key=lambda current: current.feature.value,
                )
            ]
        }
    )


def _validation_result(
    state: RestoreProjectionCacheState,
    reason: str,
) -> RestoreProjectionValidationResult:
    """Build a validation result with one explanatory reason."""

    return RestoreProjectionValidationResult(state=state, reasons=(reason,))


def _stale_keys(
    expected: Mapping[str, str],
    live: Mapping[str, str],
) -> list[str]:
    """Return keys whose cached fingerprint is missing or differs from live data."""

    stale: list[str] = []
    for key, expected_fingerprint in expected.items():
        if live.get(key) != expected_fingerprint:
            stale.append(key)
    return stale


def _unsafe_slider_range_paths(value: object) -> tuple[str, ...]:
    """Return JSON paths whose numeric metadata cannot fit a Qt slider range."""

    paths: list[str] = []
    _collect_unsafe_slider_range_paths(value, "$", paths)
    return tuple(paths)


def _collect_unsafe_slider_range_paths(
    value: object,
    path: str,
    paths: list[str],
) -> None:
    """Collect unsafe slider metadata paths from a nested JSON payload."""

    if isinstance(value, Mapping):
        if _mapping_has_unsafe_slider_range(value):
            paths.append(path)
        for key, item in value.items():
            _collect_unsafe_slider_range_paths(item, f"{path}.{key}", paths)
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _collect_unsafe_slider_range_paths(item, f"{path}[{index}]", paths)


def _mapping_has_unsafe_slider_range(value: Mapping[str, object]) -> bool:
    """Return whether one metadata mapping would overflow a Qt slider."""

    if not {"min", "max", "step"}.issubset(value):
        return False
    minimum = _float_or_none(value["min"])
    maximum = _float_or_none(value["max"])
    step = _float_or_none(value["step"])
    if minimum is None or maximum is None or step is None:
        return False
    if not all(math.isfinite(item) for item in (minimum, maximum, step)):
        return True
    if step <= 0 or maximum < minimum:
        return True
    return ((maximum - minimum) / step) > _QT_SLIDER_MAXIMUM


def _float_or_none(value: object) -> float | None:
    """Return a finite-checkable float for JSON scalar numeric metadata."""

    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (ValueError, OverflowError):
        return None


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    """Return a mapping payload or raise `ValueError` with field context."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object.")
    return value


def _sequence(value: object, field_name: str) -> tuple[object, ...]:
    """Return a sequence payload or raise `ValueError` with field context."""

    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_name} must be a list.")
    return tuple(value)


def _required_str(payload: Mapping[str, object], key: str) -> str:
    """Return a required string field from a parsed payload."""

    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _required_int(payload: Mapping[str, object], key: str) -> int:
    """Return a required integer field from a parsed payload."""

    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer.")
    return value


def _str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """Return a tuple of strings from a JSON sequence."""

    items = _sequence(value, field_name)
    strings: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings.")
        strings.append(item)
    return tuple(strings)


def _str_mapping(value: object, field_name: str) -> dict[str, str]:
    """Return a string-to-string mapping from a JSON object."""

    payload = _mapping(value, field_name)
    result: dict[str, str] = {}
    for key, item in payload.items():
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{key}] must be a string.")
        result[str(key)] = item
    return result


def _json_object(value: object, field_name: str) -> JsonObject:
    """Return a JSON object payload, defaulting missing optional objects to empty."""

    if value is None:
        return {}
    payload = _mapping(value, field_name)
    return {str(key): item for key, item in payload.items()}


def _json_safe(value: object) -> object:
    """Normalize tuples, mappings, and unsupported objects for stable hashing."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    return repr(value)


__all__ = [
    "APP_PROJECTION_VERSION",
    "RESTORE_PROJECTION_CACHE_SCHEMA_VERSION",
    "CachedCubeProjection",
    "CachedNodeProjection",
    "CachedWorkflowProjection",
    "RestoreProjectionArtifact",
    "RestoreProjectionCacheKey",
    "RestoreProjectionCacheRepository",
    "RestoreProjectionCacheState",
    "RestoreProjectionInvalidation",
    "RestoreProjectionValidationResult",
    "RestoreProjectionValidationService",
    "cube_definition_fingerprint",
    "fingerprint_json",
    "node_definition_fingerprint",
    "prompt_feature_profile_fingerprint",
    "workspace_projection_fingerprint",
]
