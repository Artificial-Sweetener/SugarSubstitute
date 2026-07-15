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

"""Extract Qt-free restored editor projection cache artifacts from live UI state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum

from substitute.application.ports import NodeDefinitionGateway
from substitute.application.workspace_state.restore_projection_cache import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    CachedCubeProjection,
    CachedNodeProjection,
    CachedWorkflowProjection,
    RestoreProjectionArtifact,
    RestoreProjectionCacheRepository,
    fingerprint_json,
    node_definition_fingerprint,
    workspace_projection_fingerprint,
)
from substitute.domain.common import JsonObject
from substitute.domain.workflow import CubeState
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot


class RestoredEditorProjectionCacheExtractor:
    """Build cache artifacts from the live validated restored editor projection."""

    def capture_and_store(
        self,
        *,
        repository: RestoreProjectionCacheRepository,
        snapshot: WorkspaceSnapshot,
        target_key: str,
        editor_panels: Mapping[str, object],
        node_definition_gateway: NodeDefinitionGateway,
    ) -> RestoreProjectionArtifact:
        """Capture live editor projection metadata and persist it through a port."""

        artifact = self.capture(
            snapshot=snapshot,
            target_key=target_key,
            editor_panels=editor_panels,
            node_definition_gateway=node_definition_gateway,
        )
        repository.save(artifact)
        return artifact

    def capture(
        self,
        *,
        snapshot: WorkspaceSnapshot,
        target_key: str,
        editor_panels: Mapping[str, object],
        node_definition_gateway: NodeDefinitionGateway,
    ) -> RestoreProjectionArtifact:
        """Return a cache artifact for a fully restored live editor projection."""

        workflows = tuple(
            self._workflow_projection(
                workflow,
                editor_panel=editor_panels.get(workflow.workflow_id),
                node_definition_gateway=node_definition_gateway,
            )
            for workflow in snapshot.workflows
        )
        node_fingerprints: dict[str, str] = {}
        cube_fingerprints: dict[str, str] = {}
        prompt_metadata: dict[str, object] = {}
        for workflow in workflows:
            for cube in workflow.cubes:
                cube_fingerprints[cube.alias] = fingerprint_json(
                    {
                        "canonical_cube_id": cube.canonical_cube_id,
                        "cube_version": cube.cube_version,
                        "content_hash": cube.content_hash,
                        "catalog_revision": cube.catalog_revision,
                        "buffer_fingerprint": cube.buffer_fingerprint,
                    }
                )
                node_fingerprints.update(cube.node_definition_fingerprint_by_class)
                if cube.prompt_field_metadata:
                    prompt_metadata[cube.alias] = cube.prompt_field_metadata
        return RestoreProjectionArtifact(
            schema_version=RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
            created_at=_utc_now_text(),
            app_projection_version=APP_PROJECTION_VERSION,
            target_key=target_key,
            workspace_fingerprint=workspace_projection_fingerprint(snapshot),
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            workflows=workflows,
            prompt_editor_feature_profile_fingerprint=fingerprint_json(prompt_metadata),
            node_definition_fingerprints=node_fingerprints,
            cube_definition_fingerprints=cube_fingerprints,
            projection={
                "active_route": snapshot.active_route,
                "active_workflow_id": snapshot.active_workflow_id,
                "workflow_count": len(workflows),
            },
        )

    def _workflow_projection(
        self,
        workflow: WorkflowSnapshot,
        *,
        editor_panel: object | None,
        node_definition_gateway: NodeDefinitionGateway,
    ) -> CachedWorkflowProjection:
        """Return cache projection data for one workflow snapshot."""

        stack_order = tuple(workflow.workflow.stack_order)
        cubes = tuple(
            self._cube_projection(
                alias,
                cube,
                editor_panel=editor_panel,
                node_definition_gateway=node_definition_gateway,
            )
            for alias in stack_order
            if (cube := workflow.workflow.cubes.get(alias)) is not None
        )
        return CachedWorkflowProjection(
            workflow_id=workflow.workflow_id,
            tab_label=workflow.tab_label,
            stack_order=stack_order,
            active_cube_alias=workflow.active_cube_alias,
            cube_aliases=tuple(cube.alias for cube in cubes),
            workflow_fingerprint=fingerprint_json(
                {
                    "workflow_id": workflow.workflow_id,
                    "stack_order": stack_order,
                }
            ),
            cubes=cubes,
        )

    def _cube_projection(
        self,
        alias: str,
        cube: CubeState,
        *,
        editor_panel: object | None,
        node_definition_gateway: NodeDefinitionGateway,
    ) -> CachedCubeProjection:
        """Return cache projection data for one cube section."""

        nodes = cube.buffer.get("nodes", {})
        node_items = nodes.items() if isinstance(nodes, dict) else ()
        projected_node_order = tuple(str(node_name) for node_name, _node in node_items)
        node_classes = tuple(
            dict.fromkeys(
                str(node.get("class_type", ""))
                for _node_name, node in node_items
                if isinstance(node, dict) and str(node.get("class_type", ""))
            )
        )
        node_fingerprints = {
            node_class: node_definition_fingerprint(
                node_definition_gateway.get_node_definition(node_class)
            )
            for node_class in node_classes
        }
        current_behavior_snapshot = getattr(
            editor_panel,
            "current_behavior_snapshot",
            None,
        )
        behavior_snapshot = (
            current_behavior_snapshot()
            if callable(current_behavior_snapshot)
            else getattr(editor_panel, "_last_behavior_snapshot", None)
        )
        field_specs_by_node = (
            getattr(behavior_snapshot, "field_specs_by_alias", {}).get(alias, {})
            if behavior_snapshot is not None
            else {}
        )
        card_decisions_by_node = (
            getattr(behavior_snapshot, "card_decisions_by_alias", {}).get(alias, {})
            if behavior_snapshot is not None
            else {}
        )
        field_specs_json: JsonObject = {}
        field_order: dict[str, tuple[str, ...]] = {}
        prompt_field_metadata: JsonObject = {}
        cached_nodes: list[CachedNodeProjection] = []
        for node_name, field_specs in field_specs_by_node.items():
            if not isinstance(field_specs, Mapping):
                continue
            node_field_order = tuple(str(field_key) for field_key in field_specs)
            field_order[str(node_name)] = node_field_order
            node_specs: JsonObject = {}
            node_prompt_metadata: JsonObject = {}
            node_class = _node_class(cube, str(node_name))
            for field_key, field_spec in field_specs.items():
                field_spec_json = _field_spec_projection(field_spec)
                node_specs[str(field_key)] = field_spec_json
                if field_spec_json.get("presentation") == "prompt_box":
                    node_prompt_metadata[str(field_key)] = {
                        "field_type": field_spec_json.get("field_type"),
                        "style": field_spec_json.get("style", {}),
                    }
            field_specs_json[str(node_name)] = node_specs
            if node_prompt_metadata:
                prompt_field_metadata[str(node_name)] = node_prompt_metadata
            cached_nodes.append(
                CachedNodeProjection(
                    node_name=str(node_name),
                    node_class=node_class,
                    field_order=node_field_order,
                    resolved_field_specs=node_specs,
                    resolved_card_visibility=_safe_json_object(
                        card_decisions_by_node.get(node_name)
                    ),
                    prompt_field_metadata=node_prompt_metadata,
                )
            )
        ui_payload = cube.ui if isinstance(cube.ui, dict) else {}
        canonical_cube = ui_payload.get("canonical_cube")
        canonical_cube_id = (
            str(canonical_cube.get("cube_id", ""))
            if isinstance(canonical_cube, dict)
            else ""
        ) or cube.cube_id
        return CachedCubeProjection(
            alias=alias,
            requested_cube_id=cube.cube_id,
            canonical_cube_id=canonical_cube_id,
            cube_version=cube.version,
            content_hash=str(ui_payload.get("content_hash", "")),
            catalog_revision=str(ui_payload.get("catalog_revision", "")),
            buffer_fingerprint=fingerprint_json(cube.buffer),
            node_classes=node_classes,
            node_definition_fingerprint_by_class=node_fingerprints,
            projected_node_order=projected_node_order,
            resolved_field_specs=field_specs_json,
            resolved_card_visibility={
                str(node_name): _safe_json_object(decision)
                for node_name, decision in card_decisions_by_node.items()
            },
            field_order=field_order,
            prompt_field_metadata=prompt_field_metadata,
            nodes=tuple(cached_nodes),
        )


def _field_spec_projection(field_spec: object) -> JsonObject:
    """Return a sanitized projection of one resolved field spec."""

    behavior = getattr(field_spec, "field_behavior", None)
    presentation = getattr(behavior, "presentation", "")
    return {
        "cube_alias": str(getattr(field_spec, "cube_alias", "")),
        "node_name": str(getattr(field_spec, "node_name", "")),
        "class_type": str(getattr(field_spec, "class_type", "")),
        "field_key": str(getattr(field_spec, "field_key", "")),
        "field_type": getattr(field_spec, "field_type", None),
        "constraints": _safe_json_object(getattr(field_spec, "constraints", {})),
        "field_info": _safe_json(getattr(field_spec, "field_info", None)),
        "value_source": _safe_json(getattr(field_spec, "value_source", "")),
        "presentation": _enum_value(presentation),
        "control_name": str(getattr(behavior, "control_name", "") or ""),
        "label_override": str(getattr(behavior, "label_override", "") or ""),
        "style": _safe_json_object(getattr(behavior, "style", {})),
    }


def _node_class(cube: CubeState, node_name: str) -> str:
    """Return the class type for one node in a cube buffer."""

    nodes = cube.buffer.get("nodes", {})
    node = nodes.get(node_name) if isinstance(nodes, dict) else None
    if not isinstance(node, dict):
        return ""
    return str(node.get("class_type", ""))


def _safe_json_object(value: object) -> JsonObject:
    """Return a sanitized JSON object or an empty object for unsupported values."""

    safe = _safe_json(value)
    return safe if isinstance(safe, dict) else {}


def _safe_json(value: object) -> object:
    """Return JSON-compatible diagnostic projection data without local paths."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_json(item)
            for key, item in value.items()
            if "path" not in str(key).casefold()
        }
    if isinstance(value, tuple | list):
        return [_safe_json(item) for item in value]
    return repr(value)


def _enum_value(value: object) -> object:
    """Return the serializable value for enum-like objects."""

    return value.value if isinstance(value, Enum) else str(value)


def _utc_now_text() -> str:
    """Return a compact UTC timestamp for cache diagnostics."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


__all__ = ["RestoredEditorProjectionCacheExtractor"]
