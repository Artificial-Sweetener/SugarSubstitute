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

"""Encode and decode workspace snapshots using explicit versioned JSON shapes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import cast
from uuid import UUID

from substitute.domain.common import JsonObject
from substitute.domain.cube_library import (
    CubeIconDescriptor,
    CubeUpdatePolicy,
)
from substitute.domain.generation.seed_control import (
    SeedControlState,
    seed_control_state_from_json,
    seed_control_state_to_json,
)
from substitute.domain.workflow import (
    CubeState,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)
from substitute.domain.workflow.canvas_models import WorkflowCanvasState
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
    CanvasLayoutSnapshot,
    EditorViewportSnapshot,
    FloatingCanvasWindowSnapshot,
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)


class SnapshotCodecError(ValueError):
    """Report invalid snapshot payloads at the JSON boundary."""


def workspace_snapshot_to_json(snapshot: WorkspaceSnapshot) -> JsonObject:
    """Return a JSON-ready mapping for one workspace snapshot."""

    return {
        "schema_version": snapshot.schema_version,
        "workflows": [
            _workflow_snapshot_to_json(workflow) for workflow in snapshot.workflows
        ],
        "tab_order": list(snapshot.tab_order),
        "active_route": snapshot.active_route,
        "active_workflow_id": snapshot.active_workflow_id,
        "shell_layout": _shell_layout_to_json(snapshot.shell_layout),
    }


def workspace_snapshot_from_json(payload: Mapping[str, object]) -> WorkspaceSnapshot:
    """Build a workspace snapshot from a decoded JSON mapping."""

    schema_version = _required_str(payload, "schema_version")
    if schema_version != WORKSPACE_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotCodecError(
            f"Unsupported workspace snapshot schema version: {schema_version}"
        )
    tab_order = tuple(str(item) for item in _required_sequence(payload, "tab_order"))
    active_route = _required_str(payload, "active_route")
    active_workflow_id = _optional_str(payload.get("active_workflow_id"))
    if active_workflow_id is None:
        active_workflow_id = _fallback_active_workflow_id(active_route, tab_order)
    return WorkspaceSnapshot(
        schema_version=schema_version,
        workflows=tuple(
            _workflow_snapshot_from_json(item)
            for item in _required_sequence(payload, "workflows")
        ),
        tab_order=tab_order,
        active_route=active_route,
        active_workflow_id=active_workflow_id,
        shell_layout=_shell_layout_from_json(payload.get("shell_layout")),
    )


def _fallback_active_workflow_id(
    active_route: str,
    tab_order: tuple[str, ...],
) -> str:
    """Infer active workflow id for snapshots written before the field existed."""

    if active_route in tab_order:
        return active_route
    return tab_order[0] if tab_order else ""


def workflow_state_to_json(state: WorkflowState) -> JsonObject:
    """Return a JSON-ready mapping for the complete internal workflow state."""

    return {
        "cubes": {
            alias: _cube_state_to_json(cube) for alias, cube in state.cubes.items()
        },
        "stack_order": list(state.stack_order),
        "metadata": _json_object_to_json(state.metadata, path="workflow.metadata"),
        "global_overrides": _json_object_to_json(
            state.global_overrides,
            path="workflow.global_overrides",
        ),
        "global_override_selections": dict(state.global_override_selections),
        "override_control_states": _seed_control_states_to_json(
            state.override_control_states
        ),
        "canvas": _canvas_state_to_json(state.canvas),
        "output_image_uuids": [str(image_id) for image_id in state.output_image_uuids],
        "output_focus_mode": state.output_focus_mode.value,
        "active_output_uuid": _uuid_to_text(state.active_output_uuid),
        "active_output_set_index": state.active_output_set_index,
        "active_output_source_key": state.active_output_source_key,
        "active_output_scene_key": state.active_output_scene_key,
        "active_output_scene_overview": state.active_output_scene_overview,
        "output_compare_state": _output_compare_state_to_json(
            state.output_compare_state
        ),
    }


def workflow_state_from_json(payload: Mapping[str, object]) -> WorkflowState:
    """Build a workflow state from a decoded JSON mapping."""

    cubes_payload = _optional_mapping(payload.get("cubes"))
    canvas_payload = _optional_mapping(payload.get("canvas"))
    return WorkflowState(
        cubes={
            str(alias): _cube_state_from_json(
                _required_mapping(value),
                alias=str(alias),
            )
            for alias, value in cubes_payload.items()
        },
        stack_order=[
            str(item) for item in _optional_sequence(payload.get("stack_order"))
        ],
        metadata=dict(_optional_mapping(payload.get("metadata"))),
        global_overrides={
            str(key): dict(_required_mapping(value))
            for key, value in _optional_mapping(payload.get("global_overrides")).items()
        },
        global_override_selections=_global_override_selections_from_json(
            payload.get("global_override_selections")
        ),
        override_control_states=_seed_control_states_from_json(
            payload.get("override_control_states")
        ),
        canvas=_canvas_state_from_json(canvas_payload),
        output_image_uuids=[
            _uuid_from_text(str(item))
            for item in _optional_sequence(payload.get("output_image_uuids"))
        ],
        output_focus_mode=_output_focus_mode_from_text(
            payload.get("output_focus_mode")
        ),
        active_output_uuid=_optional_uuid_from_value(payload.get("active_output_uuid")),
        active_output_set_index=_optional_int_with_default(
            payload.get("active_output_set_index"),
            default=1,
        ),
        active_output_source_key=_optional_str(payload.get("active_output_source_key")),
        active_output_scene_key=_optional_str(payload.get("active_output_scene_key")),
        active_output_scene_overview=bool(
            payload.get("active_output_scene_overview", False)
        ),
        output_compare_state=_output_compare_state_from_json(
            payload.get("output_compare_state")
        ),
    )


def _workflow_snapshot_to_json(snapshot: WorkflowSnapshot) -> JsonObject:
    """Return a JSON-ready mapping for one workflow tab snapshot."""

    return {
        "workflow_id": snapshot.workflow_id,
        "tab_label": snapshot.tab_label,
        "workflow": workflow_state_to_json(snapshot.workflow),
        "active_cube_alias": snapshot.active_cube_alias,
        "input_images": [
            {
                "image_id": image.image_id,
                "path": str(image.path),
                "sequence": image.sequence,
            }
            for image in snapshot.input_images
        ],
        "input_masks": [
            {
                "mask_id": mask.mask_id,
                "image_id": mask.image_id,
                "path": str(mask.path),
                "association_key": list(mask.association_key)
                if mask.association_key is not None
                else None,
            }
            for mask in snapshot.input_masks
        ],
        "output_images": [
            {
                "image_id": image.image_id,
                "path": str(image.path),
                "metadata": _image_meta_to_json(image.metadata),
                "sequence": image.sequence,
            }
            for image in snapshot.output_images
        ],
        "editor_viewport": _editor_viewport_to_json(snapshot.editor_viewport),
    }


def _workflow_snapshot_from_json(value: object) -> WorkflowSnapshot:
    """Build one workflow snapshot from a decoded JSON value."""

    payload = _required_mapping(value)
    return WorkflowSnapshot(
        workflow_id=_required_str(payload, "workflow_id"),
        tab_label=_required_str(payload, "tab_label"),
        workflow=workflow_state_from_json(_required_mapping(payload.get("workflow"))),
        active_cube_alias=_optional_str(payload.get("active_cube_alias")),
        input_images=tuple(
            _input_image_from_json(item)
            for item in _optional_sequence(payload.get("input_images"))
        ),
        input_masks=tuple(
            _input_mask_from_json(item)
            for item in _optional_sequence(payload.get("input_masks"))
        ),
        output_images=tuple(
            _output_image_from_json(item)
            for item in _optional_sequence(payload.get("output_images"))
        ),
        editor_viewport=_editor_viewport_from_json(payload.get("editor_viewport")),
    )


def _editor_viewport_to_json(
    snapshot: EditorViewportSnapshot | None,
) -> JsonObject | None:
    """Return a JSON-ready mapping for optional editor viewport state."""

    if snapshot is None:
        return None
    return {
        "scroll_value": snapshot.scroll_value,
        "scroll_maximum": snapshot.scroll_maximum,
        "anchor_cube_alias": snapshot.anchor_cube_alias,
    }


def _editor_viewport_from_json(value: object) -> EditorViewportSnapshot | None:
    """Build optional editor viewport state from a decoded JSON value."""

    if value is None:
        return None
    payload = _required_mapping(value)
    return EditorViewportSnapshot(
        scroll_value=_required_int(payload, "scroll_value"),
        scroll_maximum=_required_int(payload, "scroll_maximum"),
        anchor_cube_alias=_optional_str(payload.get("anchor_cube_alias")),
    )


def _cube_state_to_json(cube: CubeState) -> JsonObject:
    """Return a JSON-ready mapping for one cube state."""

    return {
        "cube_id": cube.cube_id,
        "version": cube.version,
        "alias": cube.alias,
        "original_cube": _json_object_to_json(
            cube.original_cube,
            path=f"cube[{cube.alias}].original_cube",
        ),
        "buffer": _json_object_to_json(
            cube.buffer,
            path=f"cube[{cube.alias}].buffer",
        ),
        "display_name": cube.display_name,
        "undo_stack": [
            _json_object_to_json(item, path=f"cube[{cube.alias}].undo_stack")
            for item in cube.undo_stack
        ],
        "redo_stack": [
            _json_object_to_json(item, path=f"cube[{cube.alias}].redo_stack")
            for item in cube.redo_stack
        ],
        "dirty": cube.dirty,
        "ui": _cube_ui_to_json(cube),
        "field_control_states": _nested_seed_control_states_to_json(
            cube.field_control_states
        ),
        "update_policy": cube.update_policy.value,
        "bypassed": cube.bypassed,
    }


def _cube_state_from_json(payload: Mapping[str, object], *, alias: str) -> CubeState:
    """Build one cube state from a decoded JSON mapping."""

    ui_payload = _cube_ui_from_json(payload.get("ui"))
    cube_id = _required_nonempty_str(
        payload,
        "cube_id",
        context=f"cube alias '{alias}'",
    )
    return CubeState(
        cube_id=cube_id,
        version=_required_nonempty_str(
            payload,
            "version",
            context=f"cube alias '{alias}' ({cube_id})",
        ),
        alias=_required_str(payload, "alias"),
        original_cube=dict(_optional_mapping(payload.get("original_cube"))),
        buffer=dict(_optional_mapping(payload.get("buffer"))),
        display_name=_optional_str(payload.get("display_name")) or "",
        undo_stack=[
            dict(_required_mapping(item))
            for item in _optional_sequence(payload.get("undo_stack"))
        ],
        redo_stack=[
            dict(_required_mapping(item))
            for item in _optional_sequence(payload.get("redo_stack"))
        ],
        dirty=bool(payload.get("dirty", False)),
        ui=ui_payload,
        field_control_states=_nested_seed_control_states_from_json(
            payload.get("field_control_states")
        ),
        update_policy=_cube_update_policy_from_json(payload.get("update_policy")),
        bypassed=payload.get("bypassed") is True,
    )


def _seed_control_states_to_json(
    states: Mapping[str, SeedControlState],
) -> JsonObject:
    """Return JSON-ready seed control states keyed by owner identity."""

    return {
        str(key): seed_control_state_to_json(state) for key, state in states.items()
    }


def _seed_control_states_from_json(value: object) -> dict[str, SeedControlState]:
    """Build seed control states from decoded JSON mapping."""

    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): seed_control_state_from_json(state) for key, state in value.items()
    }


def _nested_seed_control_states_to_json(
    states: Mapping[str, Mapping[str, SeedControlState]],
) -> JsonObject:
    """Return JSON-ready node/field seed control state mappings."""

    return {
        str(node_name): _seed_control_states_to_json(field_states)
        for node_name, field_states in states.items()
    }


def _nested_seed_control_states_from_json(
    value: object,
) -> dict[str, dict[str, SeedControlState]]:
    """Build node/field seed control state mappings from decoded JSON."""

    if not isinstance(value, Mapping):
        return {}
    nested: dict[str, dict[str, SeedControlState]] = {}
    for node_name, field_states in value.items():
        if not isinstance(field_states, Mapping):
            continue
        nested[str(node_name)] = _seed_control_states_from_json(field_states)
    return nested


def _cube_ui_to_json(cube: CubeState) -> JsonObject | None:
    """Return persistent cube UI metadata without runtime-only collaborators."""

    if cube.ui is None:
        return None
    return {
        key: _json_value_to_json(value, path=f"cube[{cube.alias}].ui.{key}")
        for key, value in cube.ui.items()
        if key != "node_behavior_runtime"
    }


def _cube_ui_from_json(value: object) -> dict[str, object] | None:
    """Build cube UI metadata and restore known descriptor-like values."""

    if value is None:
        return None
    payload = dict(_required_mapping(value))
    icon_payload = payload.get("cube_icon")
    if isinstance(icon_payload, Mapping):
        payload["cube_icon"] = _cube_icon_descriptor_from_json(icon_payload)
    return payload


def _cube_update_policy_from_json(value: object) -> CubeUpdatePolicy:
    """Build the cube update policy stored for one workflow cube."""

    if not isinstance(value, str) or not value:
        return CubeUpdatePolicy.PINNED
    try:
        return CubeUpdatePolicy(value)
    except ValueError as error:
        raise SnapshotCodecError(f"Unsupported cube update policy: {value}") from error


def _cube_icon_descriptor_to_json(descriptor: CubeIconDescriptor) -> JsonObject:
    """Return a JSON-ready mapping for a cube icon descriptor."""

    return {
        "kind": descriptor.kind,
        "url": descriptor.url,
        "media_type": descriptor.media_type,
        "repo_relative_path": descriptor.repo_relative_path,
        "color_behavior": descriptor.color_behavior,
    }


def _cube_icon_descriptor_from_json(
    payload: Mapping[str, object],
) -> CubeIconDescriptor:
    """Build a cube icon descriptor from persisted cube UI metadata."""

    return CubeIconDescriptor(
        kind=_optional_str(payload.get("kind")) or "",
        url=_optional_str(payload.get("url")) or "",
        media_type=_optional_str(payload.get("media_type")) or "",
        repo_relative_path=_optional_str(payload.get("repo_relative_path")) or "",
        color_behavior=_optional_str(payload.get("color_behavior")) or "auto",
    )


def _canvas_state_to_json(canvas: WorkflowCanvasState) -> JsonObject:
    """Return a JSON-ready mapping for workflow canvas state."""

    return {
        "mask_associations": [
            {
                "cube_alias": cube_alias,
                "node_name": node_name,
                "mask_id": str(mask_id),
            }
            for (cube_alias, node_name), mask_id in canvas.mask_associations.items()
        ],
        "mask_to_image_map": [
            {"mask_id": str(mask_id), "image_id": str(image_id)}
            for mask_id, image_id in canvas.mask_to_image_map.items()
        ],
        "input_key_map": [
            {"input_key": input_key, "image_id": str(image_id)}
            for input_key, image_id in canvas.input_key_map.items()
        ],
        "input_image_uuid": _uuid_to_text(canvas.input_image_uuid),
        "active_input_mask_uuid": _uuid_to_text(canvas.active_input_mask_uuid),
        "active_canvas_route": canvas.active_canvas_route,
    }


def _canvas_state_from_json(payload: Mapping[str, object]) -> WorkflowCanvasState:
    """Build workflow canvas state from a decoded JSON mapping."""

    return WorkflowCanvasState(
        mask_associations={
            (
                _required_str(_required_mapping(item), "cube_alias"),
                _required_str(_required_mapping(item), "node_name"),
            ): _uuid_from_text(_required_str(_required_mapping(item), "mask_id"))
            for item in _optional_sequence(payload.get("mask_associations"))
        },
        mask_to_image_map={
            _uuid_from_text(_required_str(_required_mapping(item), "mask_id")): (
                _uuid_from_text(_required_str(_required_mapping(item), "image_id"))
            )
            for item in _optional_sequence(payload.get("mask_to_image_map"))
        },
        input_key_map={
            _required_str(_required_mapping(item), "input_key"): _uuid_from_text(
                _required_str(_required_mapping(item), "image_id")
            )
            for item in _optional_sequence(payload.get("input_key_map"))
        },
        input_image_uuid=_optional_uuid_from_value(payload.get("input_image_uuid")),
        active_input_mask_uuid=_optional_uuid_from_value(
            payload.get("active_input_mask_uuid")
        ),
        active_canvas_route=_optional_str(payload.get("active_canvas_route")),
    )


def _image_meta_to_json(metadata: ImageMetaSnapshot) -> JsonObject:
    """Return a JSON-ready mapping for output image metadata."""

    return {
        "workflow_name": metadata.workflow_name,
        "cube_name": metadata.cube_name,
        "image_number": metadata.image_number,
        "suffix": metadata.suffix,
        "path": str(metadata.path),
        "source_key": metadata.source_key,
        "source_label": metadata.source_label,
        "node_id": metadata.node_id,
        "generation_run_id": metadata.generation_run_id,
        "prompt_id": metadata.prompt_id,
        "client_id": metadata.client_id,
        "list_index": metadata.list_index,
        "scene_run_id": metadata.scene_run_id,
        "scene_key": metadata.scene_key,
        "scene_title": metadata.scene_title,
        "scene_order": metadata.scene_order,
        "scene_count": metadata.scene_count,
        "width": metadata.width,
        "height": metadata.height,
        "cube_execution_duration_ms": metadata.cube_execution_duration_ms,
    }


def _image_meta_from_json(value: object) -> ImageMetaSnapshot:
    """Build output image metadata from a decoded JSON value."""

    payload = _required_mapping(value)
    return ImageMetaSnapshot(
        workflow_name=_required_str(payload, "workflow_name"),
        cube_name=_required_str(payload, "cube_name"),
        image_number=_required_int(payload, "image_number"),
        suffix=_required_str(payload, "suffix"),
        path=Path(_required_str(payload, "path")),
        source_key=_optional_str(payload.get("source_key")) or "",
        source_label=_optional_str(payload.get("source_label")) or "",
        node_id=_optional_str(payload.get("node_id")) or "",
        generation_run_id=_optional_str(payload.get("generation_run_id")) or "",
        prompt_id=_optional_str(payload.get("prompt_id")) or "",
        client_id=_optional_str(payload.get("client_id")) or "",
        list_index=_optional_int(payload.get("list_index"), default=None),
        scene_run_id=_optional_str(payload.get("scene_run_id")),
        scene_key=_optional_str(payload.get("scene_key")),
        scene_title=_optional_str(payload.get("scene_title")),
        scene_order=_optional_int(payload.get("scene_order"), default=None),
        scene_count=_optional_int(payload.get("scene_count"), default=None),
        width=_optional_int(payload.get("width"), default=None),
        height=_optional_int(payload.get("height"), default=None),
        cube_execution_duration_ms=_optional_float(
            payload.get("cube_execution_duration_ms")
        ),
    )


def _input_image_from_json(value: object) -> InputImageReference:
    """Build one input image reference from a decoded JSON value."""

    payload = _required_mapping(value)
    return InputImageReference(
        image_id=_required_str(payload, "image_id"),
        path=Path(_required_str(payload, "path")),
        sequence=_required_int(payload, "sequence"),
    )


def _input_mask_from_json(value: object) -> InputMaskReference:
    """Build one input mask reference from a decoded JSON value."""

    payload = _required_mapping(value)
    association_value = payload.get("association_key")
    association_key: tuple[str, str] | None = None
    if association_value is not None:
        association_sequence = _required_sequence_value(association_value)
        if len(association_sequence) != 2:
            raise SnapshotCodecError("association_key must have two string items")
        association_key = (str(association_sequence[0]), str(association_sequence[1]))
    return InputMaskReference(
        mask_id=_required_str(payload, "mask_id"),
        image_id=_required_str(payload, "image_id"),
        path=Path(_required_str(payload, "path")),
        association_key=association_key,
    )


def _output_image_from_json(value: object) -> OutputImageReference:
    """Build one output image reference from a decoded JSON value."""

    payload = _required_mapping(value)
    return OutputImageReference(
        image_id=_required_str(payload, "image_id"),
        path=Path(_required_str(payload, "path")),
        metadata=_image_meta_from_json(payload.get("metadata")),
        sequence=_required_int(payload, "sequence"),
    )


def _shell_layout_to_json(snapshot: ShellLayoutSnapshot | None) -> JsonObject | None:
    """Return a JSON-ready mapping for optional shell layout state."""

    if snapshot is None:
        return None
    geometry = snapshot.geometry
    return {
        "layout_schema_version": snapshot.layout_schema_version,
        "geometry": (
            {
                "x": geometry.x,
                "y": geometry.y,
                "width": geometry.width,
                "height": geometry.height,
            }
            if geometry is not None
            else None
        ),
        "window_display_state": snapshot.window_display_state,
        "maximized": snapshot.maximized,
        "main_splitter_sizes": list(snapshot.main_splitter_sizes),
        "editor_output_splitter_sizes": list(snapshot.editor_output_splitter_sizes),
        "cube_stack_width": snapshot.cube_stack_width,
        "editor_panel_width": snapshot.editor_panel_width,
        "canvas_panel_width": snapshot.canvas_panel_width,
        "cube_stack_compact": snapshot.cube_stack_compact,
        "comfy_output_panel_visible": snapshot.comfy_output_panel_visible,
        "output_panel_height": snapshot.output_panel_height,
        "side_panel_visible": snapshot.side_panel_visible,
        "side_panel_width": snapshot.side_panel_width,
        "generation_queue_panel_visible": snapshot.generation_queue_panel_visible,
        "generation_queue_panel_width": snapshot.generation_queue_panel_width,
        "canvas_layout": _canvas_layout_to_json(snapshot.canvas_layout),
    }


def _shell_layout_from_json(value: object) -> ShellLayoutSnapshot | None:
    """Build optional shell layout state from a decoded JSON value."""

    if value is None:
        return None
    payload = _required_mapping(value)
    geometry = _window_geometry_from_json(payload.get("geometry"))
    maximized = bool(payload.get("maximized", False))
    return ShellLayoutSnapshot(
        layout_schema_version=_optional_int_with_default(
            payload.get("layout_schema_version"),
            default=1,
        ),
        geometry=geometry,
        window_display_state=_shell_window_display_state_from_json(
            payload.get("window_display_state"),
            maximized=maximized,
        ),
        maximized=maximized,
        main_splitter_sizes=tuple(
            _int_from_value(item)
            for item in _optional_sequence(payload.get("main_splitter_sizes"))
        ),
        editor_output_splitter_sizes=tuple(
            _int_from_value(item)
            for item in _optional_sequence(payload.get("editor_output_splitter_sizes"))
        ),
        cube_stack_width=_optional_positive_int(
            payload.get("cube_stack_width"),
            field_name="cube_stack_width",
        ),
        editor_panel_width=_optional_positive_int(
            payload.get("editor_panel_width"),
            field_name="editor_panel_width",
        ),
        canvas_panel_width=_optional_positive_int(
            payload.get("canvas_panel_width"),
            field_name="canvas_panel_width",
        ),
        cube_stack_compact=bool(payload.get("cube_stack_compact", False)),
        comfy_output_panel_visible=bool(
            payload.get("comfy_output_panel_visible", False)
        ),
        output_panel_height=_optional_positive_int(
            payload.get("output_panel_height"),
            field_name="output_panel_height",
        ),
        side_panel_visible=bool(payload.get("side_panel_visible", False)),
        side_panel_width=_optional_positive_int(
            payload.get("side_panel_width"),
            field_name="side_panel_width",
        ),
        generation_queue_panel_visible=bool(
            payload.get("generation_queue_panel_visible", False)
        ),
        generation_queue_panel_width=_optional_int(
            payload.get("generation_queue_panel_width"),
            default=None,
        ),
        canvas_layout=_canvas_layout_from_json(payload.get("canvas_layout")),
    )


def _canvas_layout_to_json(snapshot: CanvasLayoutSnapshot | None) -> JsonObject | None:
    """Return a JSON-ready canvas layout payload."""

    if snapshot is None:
        return None
    return {
        "floating_windows": [
            _floating_canvas_window_to_json(floating_window)
            for floating_window in snapshot.floating_windows
        ],
    }


def _canvas_layout_from_json(value: object) -> CanvasLayoutSnapshot | None:
    """Build optional canvas layout state from a decoded JSON value."""

    if value is None:
        return None
    payload = _required_mapping(value)
    return CanvasLayoutSnapshot(
        floating_windows=tuple(
            _floating_canvas_window_from_json(item)
            for item in _optional_sequence(payload.get("floating_windows"))
        )
    )


def _floating_canvas_window_to_json(
    snapshot: FloatingCanvasWindowSnapshot,
) -> JsonObject:
    """Return a JSON-ready floating canvas window payload."""

    return {
        "label": snapshot.label,
        "geometry": _window_geometry_to_json(snapshot.geometry),
        "window_display_state": snapshot.window_display_state,
        "output_generation_controls_revealed": (
            snapshot.output_generation_controls_revealed
        ),
    }


def _floating_canvas_window_from_json(
    value: object,
) -> FloatingCanvasWindowSnapshot:
    """Build one floating canvas window snapshot from JSON."""

    payload = _required_mapping(value)
    return FloatingCanvasWindowSnapshot(
        label=_required_str(payload, "label"),
        geometry=_window_geometry_from_json(payload.get("geometry")),
        window_display_state=_floating_window_display_state_from_json(
            payload.get("window_display_state")
        ),
        output_generation_controls_revealed=bool(
            payload.get("output_generation_controls_revealed", False)
        ),
    )


def _window_geometry_to_json(
    geometry: WindowGeometrySnapshot | None,
) -> JsonObject | None:
    """Return JSON-ready window geometry."""

    if geometry is None:
        return None
    return {
        "x": geometry.x,
        "y": geometry.y,
        "width": geometry.width,
        "height": geometry.height,
    }


def _shell_window_display_state_from_json(
    value: object,
    *,
    maximized: bool,
) -> str:
    """Return a supported shell display state with legacy maximized fallback."""

    if value is None:
        return "maximized" if maximized else "normal"
    if value in {"normal", "maximized", "fullscreen"}:
        return str(value)
    raise SnapshotCodecError(f"Invalid window_display_state value: {value}")


def _floating_window_display_state_from_json(value: object) -> str:
    """Return a supported floating window display state with tolerant fallback."""

    if value in {"normal", "maximized", "fullscreen"}:
        return str(value)
    return "normal"


def _window_geometry_from_json(value: object) -> WindowGeometrySnapshot | None:
    """Build optional window geometry from a decoded JSON value."""

    if value is None:
        return None
    payload = _required_mapping(value)
    return WindowGeometrySnapshot(
        x=_required_int(payload, "x"),
        y=_required_int(payload, "y"),
        width=_required_int(payload, "width"),
        height=_required_int(payload, "height"),
    )


def _output_focus_mode_from_text(value: object) -> OutputFocusMode:
    """Return a supported output focus mode or a conservative default."""

    if value == OutputFocusMode.MANUAL.value:
        return OutputFocusMode.MANUAL
    return OutputFocusMode.AUTOMATIC


def _output_compare_state_to_json(state: OutputCompareState) -> JsonObject:
    """Return a JSON-ready output compare state payload."""

    return {
        "enabled": state.enabled,
        "base": _output_compare_selection_to_json(state.base),
        "comparison": _output_compare_selection_to_json(state.comparison),
        "split_position": state.split_position,
        "orientation": state.orientation,
    }


def _output_compare_selection_to_json(
    selection: OutputCompareSelection | None,
) -> JsonObject | None:
    """Return a JSON-ready output compare selection payload."""

    if selection is None:
        return None
    return {
        "scene_key": selection.scene_key,
        "set_index": selection.set_index,
        "source_key": selection.source_key,
    }


def _output_compare_state_from_json(value: object) -> OutputCompareState:
    """Build output compare state from an optional decoded JSON payload."""

    if value is None:
        return OutputCompareState()
    payload = _required_mapping(value)
    return OutputCompareState(
        enabled=bool(payload.get("enabled", False)),
        base=_output_compare_selection_from_json(payload.get("base")),
        comparison=_output_compare_selection_from_json(payload.get("comparison")),
        split_position=_optional_float_with_default(
            payload.get("split_position"),
            default=0.5,
        ),
        orientation=_output_compare_orientation_from_json(payload.get("orientation")),
    )


def _output_compare_selection_from_json(
    value: object,
) -> OutputCompareSelection | None:
    """Build one optional output compare selection from JSON."""

    if value is None:
        return None
    payload = _required_mapping(value)
    return OutputCompareSelection(
        scene_key=_optional_str(payload.get("scene_key")),
        set_index=_optional_int_with_default(payload.get("set_index"), default=1),
        source_key=str(payload.get("source_key") or ""),
    )


def _optional_float_with_default(value: object, *, default: float) -> float:
    """Return a float value when JSON provided one, otherwise ``default``."""

    if value is None:
        return default
    if not isinstance(value, int | float | str):
        raise SnapshotCodecError(f"Invalid float value: {value}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SnapshotCodecError(f"Invalid float value: {value}") from exc


def _optional_float(value: object) -> float | None:
    """Return a float value when JSON provided one, otherwise ``None``."""

    if value is None:
        return None
    return _optional_float_with_default(value, default=0.0)


def _output_compare_orientation_from_json(value: object) -> str:
    """Return a supported output compare orientation."""

    text = str(value or "vertical")
    return text if text in {"vertical", "horizontal"} else "vertical"


def _global_override_selections_from_json(value: object) -> dict[str, bool]:
    """Build a strict global override selection map from decoded JSON."""

    selections: dict[str, bool] = {}
    for key, selected in _optional_mapping(value).items():
        if not isinstance(selected, bool):
            raise SnapshotCodecError(
                f"Invalid global override selection value for key: {key}"
            )
        selections[str(key)] = selected
    return selections


def _json_object_to_json(value: Mapping[str, object], *, path: str) -> JsonObject:
    """Return a JSON-ready copy of a loose internal metadata mapping."""

    return {
        str(item_key): _json_value_to_json(
            item_value,
            path=f"{path}.{item_key}",
        )
        for item_key, item_value in value.items()
    }


def _json_value_to_json(value: object, *, path: str) -> object:
    """Return a JSON-ready value or fail with the metadata path."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        enum_value = value.value
        if isinstance(enum_value, (str, int, float, bool)):
            return enum_value
        raise SnapshotCodecError(f"Unsupported enum value at {path}")
    if isinstance(value, CubeIconDescriptor):
        return _cube_icon_descriptor_to_json(value)
    if isinstance(value, Mapping):
        return _json_object_to_json(
            cast(Mapping[str, object], value),
            path=path,
        )
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [_json_value_to_json(item, path=f"{path}[]") for item in value]
    raise SnapshotCodecError(
        f"Unsupported JSON snapshot value at {path}: {type(value).__name__}"
    )


def _uuid_to_text(value: UUID | None) -> str | None:
    """Return UUID text when a UUID exists."""

    return str(value) if value is not None else None


def _uuid_from_text(value: str) -> UUID:
    """Parse one UUID string or raise a snapshot codec error."""

    try:
        return UUID(value)
    except ValueError as error:
        raise SnapshotCodecError(f"Invalid UUID value: {value}") from error


def _optional_uuid_from_value(value: object) -> UUID | None:
    """Parse optional UUID text from a decoded JSON value."""

    if value is None:
        return None
    return _uuid_from_text(str(value))


def _required_str(payload: Mapping[str, object], key: str) -> str:
    """Return one required string field from a mapping."""

    value = payload.get(key)
    if not isinstance(value, str):
        raise SnapshotCodecError(f"Missing or invalid string field: {key}")
    return value


def _required_nonempty_str(
    payload: Mapping[str, object],
    key: str,
    *,
    context: str,
) -> str:
    """Return one non-empty required string field from a mapping."""

    value = _required_str(payload, key).strip()
    if not value:
        raise SnapshotCodecError(f"Missing exact ref field {key} for {context}.")
    return value


def _optional_str(value: object) -> str | None:
    """Return optional string text from a decoded JSON value."""

    return value if isinstance(value, str) else None


def _required_int(payload: Mapping[str, object], key: str) -> int:
    """Return one required integer field from a mapping."""

    value = payload.get(key)
    if not isinstance(value, int):
        raise SnapshotCodecError(f"Missing or invalid integer field: {key}")
    return value


def _optional_int(value: object, *, default: int | None) -> int | None:
    """Return optional integer text from a decoded JSON value."""

    if value is None:
        return default
    if isinstance(value, int):
        return value
    raise SnapshotCodecError(f"Invalid integer value: {value}")


def _optional_positive_int(value: object, *, field_name: str) -> int | None:
    """Return an optional non-negative shell layout dimension."""

    parsed = _optional_int(value, default=None)
    if parsed is None:
        return None
    if parsed < 0:
        raise SnapshotCodecError(f"Invalid negative integer field: {field_name}")
    return parsed


def _optional_int_with_default(value: object, *, default: int) -> int:
    """Return optional integer text using a non-null default."""

    parsed = _optional_int(value, default=default)
    if parsed is None:
        return default
    return parsed


def _int_from_value(value: object) -> int:
    """Return one integer array item from a decoded JSON value."""

    if not isinstance(value, int):
        raise SnapshotCodecError(f"Invalid integer value: {value}")
    return value


def _required_mapping(value: object) -> Mapping[str, object]:
    """Return a decoded JSON object or raise a codec error."""

    if not isinstance(value, Mapping):
        raise SnapshotCodecError("Expected JSON object")
    return cast(Mapping[str, object], value)


def _optional_mapping(value: object) -> Mapping[str, object]:
    """Return a decoded JSON object or an empty mapping when absent."""

    if value is None:
        return {}
    return _required_mapping(value)


def _required_sequence(payload: Mapping[str, object], key: str) -> Sequence[object]:
    """Return one required JSON array field from a mapping."""

    return _required_sequence_value(payload.get(key))


def _optional_sequence(value: object) -> Sequence[object]:
    """Return a decoded JSON array or an empty sequence when absent."""

    if value is None:
        return ()
    return _required_sequence_value(value)


def _required_sequence_value(value: object) -> Sequence[object]:
    """Return a decoded JSON array value or raise a codec error."""

    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SnapshotCodecError("Expected JSON array")
    return value


__all__ = [
    "SnapshotCodecError",
    "workflow_state_from_json",
    "workflow_state_to_json",
    "workspace_snapshot_from_json",
    "workspace_snapshot_to_json",
]
