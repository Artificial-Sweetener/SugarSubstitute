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

"""Own deterministic identities used by restore projection invalidation."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json

from substitute.application.cubes import LoadedCubeDefinition
from substitute.domain.prompt import PromptEditorFeatureProfile
from substitute.domain.workflow import WorkflowDocumentKind
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot


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
    """Return the complete render-relevant workspace projection identity."""

    workflows_by_id = {
        workflow.workflow_id: workflow for workflow in snapshot.workflows
    }
    workflow_order = snapshot.tab_order or tuple(workflows_by_id)
    return fingerprint_json(
        {
            "schema_version": snapshot.schema_version,
            "active_route": snapshot.active_route,
            "active_workflow_id": snapshot.active_workflow_id,
            "tab_order": list(snapshot.tab_order),
            "workflows": [
                workflow_projection_identity(workflow)
                for workflow_id in workflow_order
                if (workflow := workflows_by_id.get(workflow_id)) is not None
            ],
        }
    )


def workflow_projection_fingerprint(workflow: WorkflowSnapshot) -> str:
    """Return the render-relevant identity for one workflow tab."""

    return fingerprint_json(workflow_projection_identity(workflow))


def workflow_projection_identity(workflow: WorkflowSnapshot) -> dict[str, object]:
    """Return the discriminated render identity for one workflow tab."""

    state = workflow.workflow
    identity: dict[str, object] = {
        "workflow_id": workflow.workflow_id,
        "tab_label": workflow.tab_label,
        "document_kind": state.document_kind.value,
        "global_overrides": state.global_overrides,
        "global_override_selections": state.global_override_selections,
    }
    if state.document_kind is WorkflowDocumentKind.DIRECT_COMFY:
        direct = state.direct_workflow
        if direct is None:
            raise ValueError(
                "Direct workflow identity requires direct authoring state."
            )
        identity["direct_workflow"] = {
            "buffer_fingerprint": fingerprint_json(direct.buffer),
            "durable_ui_fingerprint": fingerprint_json(
                durable_direct_workflow_ui(direct.ui)
            ),
        }
        return identity
    identity["cube_stack"] = {
        "stack_order": list(state.stack_order),
        "cubes": [
            cube_projection_identity(alias, cube)
            for alias in state.stack_order
            if (cube := state.cubes.get(alias)) is not None
        ],
    }
    return identity


def cube_projection_identity(alias: str, cube: object) -> dict[str, object]:
    """Return render-relevant identity for one cube section."""

    return {
        "alias": alias,
        "cube_id": str(getattr(cube, "cube_id", "")),
        "version": str(getattr(cube, "version", "")),
        "display_name": str(getattr(cube, "display_name", "")),
        "buffer_fingerprint": fingerprint_json(getattr(cube, "buffer", {})),
        "bypassed": bool(getattr(cube, "bypassed", False)),
        "content_hash": _cube_ui_text(cube, "content_hash"),
        "catalog_revision": _cube_ui_text(cube, "catalog_revision"),
    }


def cube_projection_cache_key(workflow_id: str, alias: str) -> str:
    """Return a collision-free cache key for one workflow-owned cube alias."""

    return f"{workflow_id}:{alias}"


def durable_direct_workflow_ui(ui: Mapping[str, object]) -> dict[str, object]:
    """Return direct UI state that is durable and can affect editor projection."""

    return {
        str(key): value for key, value in ui.items() if key != "node_behavior_runtime"
    }


def cube_definition_fingerprint(definition: LoadedCubeDefinition) -> str:
    """Return a stable fingerprint for one live loaded cube definition."""

    ui_payload = (
        definition.ui_payload if isinstance(definition.ui_payload, dict) else {}
    )
    canonical_cube = ui_payload.get("canonical_cube")
    canonical_cube_id = (
        str(canonical_cube.get("cube_id", ""))
        if isinstance(canonical_cube, dict)
        else ""
    ) or definition.cube_id
    return fingerprint_json(
        {
            "canonical_cube_id": canonical_cube_id,
            "version": definition.version,
            "content_hash": str(ui_payload.get("content_hash", "")),
            "catalog_revision": str(ui_payload.get("catalog_revision", "")),
            "graph": definition.graph,
        }
    )


def node_definition_fingerprint(payload: Mapping[str, object]) -> str:
    """Return a stable fingerprint for one live Comfy node definition."""

    return fingerprint_json(payload)


def prompt_feature_profile_fingerprint(
    profile: PromptEditorFeatureProfile,
) -> str:
    """Return the prompt feature-profile identity used by cached field metadata."""

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


def _cube_ui_text(cube: object, key: str) -> str:
    """Return one cube UI identity field as text."""

    ui_payload = getattr(cube, "ui", None)
    if not isinstance(ui_payload, dict):
        return ""
    return str(ui_payload.get(key, ""))


def _json_safe(value: object) -> object:
    """Return recursively JSON-compatible deterministic data."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    return repr(value)


__all__ = [
    "cube_definition_fingerprint",
    "cube_projection_cache_key",
    "durable_direct_workflow_ui",
    "fingerprint_json",
    "node_definition_fingerprint",
    "prompt_feature_profile_fingerprint",
    "workflow_projection_fingerprint",
    "workspace_projection_fingerprint",
]
