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

"""Serialize and deserialize versioned restore projection cache artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from substitute.application.workspace_state.restore_projection_models import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    CachedCubeProjection,
    CachedCubeStackProjection,
    CachedDirectWorkflowProjection,
    CachedEditorSectionProjection,
    CachedNodeProjection,
    CachedWorkflowProjection,
    RestoreProjectionArtifact,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import WorkflowDocumentKind


def restore_projection_artifact_to_json(
    artifact: RestoreProjectionArtifact,
) -> JsonObject:
    """Serialize one complete restore projection artifact."""

    return {
        "schema_version": artifact.schema_version,
        "created_at": artifact.created_at,
        "app_projection_version": artifact.app_projection_version,
        "target_key": artifact.target_key,
        "workspace_fingerprint": artifact.workspace_fingerprint,
        "active_route": artifact.active_route,
        "active_workflow_id": artifact.active_workflow_id,
        "workflows": [_workflow_to_json(item) for item in artifact.workflows],
        "prompt_editor_feature_profile_fingerprint": (
            artifact.prompt_editor_feature_profile_fingerprint
        ),
        "node_definition_fingerprints": dict(artifact.node_definition_fingerprints),
        "cube_definition_fingerprints": dict(artifact.cube_definition_fingerprints),
        "projection": artifact.projection,
    }


def restore_projection_artifact_from_json(value: object) -> RestoreProjectionArtifact:
    """Deserialize one artifact and enforce current cache versions."""

    payload = _mapping(value, "restore projection artifact")
    schema_version = _required_int(payload, "schema_version")
    if schema_version != RESTORE_PROJECTION_CACHE_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported restore projection schema_version {schema_version}."
        )
    app_projection_version = _required_int(payload, "app_projection_version")
    if app_projection_version != APP_PROJECTION_VERSION:
        raise ValueError(
            "Unsupported restore projection app_projection_version "
            f"{app_projection_version}."
        )
    return RestoreProjectionArtifact(
        schema_version=schema_version,
        created_at=_required_str(payload, "created_at"),
        app_projection_version=app_projection_version,
        target_key=_required_str(payload, "target_key"),
        workspace_fingerprint=_required_str(payload, "workspace_fingerprint"),
        active_route=_required_str(payload, "active_route"),
        active_workflow_id=_required_str(payload, "active_workflow_id"),
        workflows=tuple(
            _workflow_from_json(item)
            for item in _sequence(payload.get("workflows"), "workflows")
        ),
        prompt_editor_feature_profile_fingerprint=_required_str(
            payload, "prompt_editor_feature_profile_fingerprint"
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


def _workflow_to_json(workflow: CachedWorkflowProjection) -> JsonObject:
    """Serialize one discriminated workflow projection."""

    return {
        "workflow_id": workflow.workflow_id,
        "tab_label": workflow.tab_label,
        "document_kind": workflow.document_kind.value,
        "workflow_fingerprint": workflow.workflow_fingerprint,
        "cube_stack": (
            None
            if workflow.cube_stack is None
            else _cube_stack_to_json(workflow.cube_stack)
        ),
        "direct_workflow": (
            None
            if workflow.direct_workflow is None
            else _direct_workflow_to_json(workflow.direct_workflow)
        ),
    }


def _workflow_from_json(value: object) -> CachedWorkflowProjection:
    """Deserialize one discriminated workflow projection."""

    payload = _mapping(value, "cached workflow projection")
    try:
        document_kind = WorkflowDocumentKind(_required_str(payload, "document_kind"))
    except ValueError as error:
        raise ValueError("Unsupported cached workflow document kind.") from error
    cube_payload = payload.get("cube_stack")
    direct_payload = payload.get("direct_workflow")
    return CachedWorkflowProjection(
        workflow_id=_required_str(payload, "workflow_id"),
        tab_label=_required_str(payload, "tab_label"),
        document_kind=document_kind,
        workflow_fingerprint=_required_str(payload, "workflow_fingerprint"),
        cube_stack=(
            None if cube_payload is None else _cube_stack_from_json(cube_payload)
        ),
        direct_workflow=(
            None
            if direct_payload is None
            else _direct_workflow_from_json(direct_payload)
        ),
    )


def _cube_stack_to_json(stack: CachedCubeStackProjection) -> JsonObject:
    """Serialize one cube-stack projection."""

    return {
        "stack_order": list(stack.stack_order),
        "active_cube_alias": stack.active_cube_alias,
        "cubes": [_cube_to_json(cube) for cube in stack.cubes],
    }


def _cube_stack_from_json(value: object) -> CachedCubeStackProjection:
    """Deserialize one cube-stack projection."""

    payload = _mapping(value, "cached cube stack projection")
    active_alias = payload.get("active_cube_alias")
    if active_alias is not None and not isinstance(active_alias, str):
        raise ValueError("active_cube_alias must be a string or null.")
    return CachedCubeStackProjection(
        stack_order=_str_tuple(payload.get("stack_order"), "stack_order"),
        active_cube_alias=active_alias,
        cubes=tuple(
            _cube_from_json(cube)
            for cube in _sequence(payload.get("cubes", ()), "cubes")
        ),
    )


def _cube_to_json(cube: CachedCubeProjection) -> JsonObject:
    """Serialize one cube identity and editor section."""

    return {
        "requested_cube_id": cube.requested_cube_id,
        "canonical_cube_id": cube.canonical_cube_id,
        "cube_version": cube.cube_version,
        "content_hash": cube.content_hash,
        "catalog_revision": cube.catalog_revision,
        "section": _section_to_json(cube.section),
    }


def _cube_from_json(value: object) -> CachedCubeProjection:
    """Deserialize one cube identity and editor section."""

    payload = _mapping(value, "cached cube projection")
    return CachedCubeProjection(
        requested_cube_id=_required_str(payload, "requested_cube_id"),
        canonical_cube_id=_required_str(payload, "canonical_cube_id"),
        cube_version=_required_str(payload, "cube_version"),
        content_hash=_required_str(payload, "content_hash"),
        catalog_revision=_required_str(payload, "catalog_revision"),
        section=_section_from_json(payload.get("section")),
    )


def _direct_workflow_to_json(
    direct: CachedDirectWorkflowProjection,
) -> JsonObject:
    """Serialize one direct-document projection."""

    return {
        "durable_ui_fingerprint": direct.durable_ui_fingerprint,
        "section": _section_to_json(direct.section),
    }


def _direct_workflow_from_json(value: object) -> CachedDirectWorkflowProjection:
    """Deserialize one direct-document projection."""

    payload = _mapping(value, "cached direct workflow projection")
    return CachedDirectWorkflowProjection(
        durable_ui_fingerprint=_required_str(payload, "durable_ui_fingerprint"),
        section=_section_from_json(payload.get("section")),
    )


def _section_to_json(section: CachedEditorSectionProjection) -> JsonObject:
    """Serialize one common editor-section projection."""

    return {
        "section_key": section.section_key,
        "buffer_fingerprint": section.buffer_fingerprint,
        "node_classes": list(section.node_classes),
        "node_definition_fingerprint_by_class": dict(
            section.node_definition_fingerprint_by_class
        ),
        "projected_node_order": list(section.projected_node_order),
        "resolved_field_specs": section.resolved_field_specs,
        "resolved_card_visibility": section.resolved_card_visibility,
        "field_order": {
            node_name: list(fields) for node_name, fields in section.field_order.items()
        },
        "prompt_field_metadata": section.prompt_field_metadata,
        "nodes": [_node_to_json(node) for node in section.nodes],
    }


def _section_from_json(value: object) -> CachedEditorSectionProjection:
    """Deserialize one common editor-section projection."""

    payload = _mapping(value, "cached editor section projection")
    return CachedEditorSectionProjection(
        section_key=_required_str(payload, "section_key"),
        buffer_fingerprint=_required_str(payload, "buffer_fingerprint"),
        node_classes=_str_tuple(payload.get("node_classes"), "node_classes"),
        node_definition_fingerprint_by_class=_str_mapping(
            payload.get("node_definition_fingerprint_by_class"),
            "node_definition_fingerprint_by_class",
        ),
        projected_node_order=_str_tuple(
            payload.get("projected_node_order"), "projected_node_order"
        ),
        resolved_field_specs=_json_object(
            payload.get("resolved_field_specs"), "resolved_field_specs"
        ),
        resolved_card_visibility=_json_object(
            payload.get("resolved_card_visibility"), "resolved_card_visibility"
        ),
        field_order={
            str(node_name): _str_tuple(fields, f"field_order[{node_name}]")
            for node_name, fields in _mapping(
                payload.get("field_order", {}), "field_order"
            ).items()
        },
        prompt_field_metadata=_json_object(
            payload.get("prompt_field_metadata"), "prompt_field_metadata"
        ),
        nodes=tuple(
            _node_from_json(node)
            for node in _sequence(payload.get("nodes", ()), "nodes")
        ),
    )


def _node_to_json(node: CachedNodeProjection) -> JsonObject:
    """Serialize one node-card projection."""

    return {
        "node_name": node.node_name,
        "node_class": node.node_class,
        "field_order": list(node.field_order),
        "resolved_field_specs": node.resolved_field_specs,
        "resolved_card_visibility": node.resolved_card_visibility,
        "prompt_field_metadata": node.prompt_field_metadata,
    }


def _node_from_json(value: object) -> CachedNodeProjection:
    """Deserialize one node-card projection."""

    payload = _mapping(value, "cached node projection")
    return CachedNodeProjection(
        node_name=_required_str(payload, "node_name"),
        node_class=_required_str(payload, "node_class"),
        field_order=_str_tuple(payload.get("field_order"), "field_order"),
        resolved_field_specs=_json_object(
            payload.get("resolved_field_specs"), "resolved_field_specs"
        ),
        resolved_card_visibility=_json_object(
            payload.get("resolved_card_visibility"), "resolved_card_visibility"
        ),
        prompt_field_metadata=_json_object(
            payload.get("prompt_field_metadata"), "prompt_field_metadata"
        ),
    )


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    """Return a string-keyed mapping or raise `ValueError`."""

    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object.")
    return {str(key): item for key, item in value.items()}


def _sequence(value: object, field_name: str) -> tuple[object, ...]:
    """Return a non-string sequence or raise `ValueError`."""

    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError(f"{field_name} must be an array.")
    return tuple(value)


def _required_str(payload: Mapping[str, object], key: str) -> str:
    """Return one required string field."""

    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _required_int(payload: Mapping[str, object], key: str) -> int:
    """Return one required integer field."""

    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer.")
    return value


def _str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """Return an all-string tuple."""

    items = _sequence(value, field_name)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"{field_name} must contain only strings.")
    return tuple(item for item in items if isinstance(item, str))


def _str_mapping(value: object, field_name: str) -> dict[str, str]:
    """Return a string-to-string mapping."""

    payload = _mapping(value, field_name)
    if not all(isinstance(item, str) for item in payload.values()):
        raise ValueError(f"{field_name} must contain only string values.")
    return {key: item for key, item in payload.items() if isinstance(item, str)}


def _json_object(value: object, field_name: str) -> JsonObject:
    """Return a recursively JSON-compatible object mapping."""

    payload = _mapping(value, field_name)
    return {key: _json_safe(item) for key, item in payload.items()}


def _json_safe(value: object) -> object:
    """Return recursively JSON-compatible data."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    raise ValueError(f"Unsupported JSON value type {type(value).__name__}.")


__all__ = [
    "restore_projection_artifact_from_json",
    "restore_projection_artifact_to_json",
]
