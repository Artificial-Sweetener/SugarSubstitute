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

"""Parse Substitute BackEnd cube-output websocket events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, cast

from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact

MediaKind = Literal["image", "audio", "video", "value", "unknown"]


@dataclass(frozen=True)
class CubeOutputEvent:
    """Describe one parsed Substitute cube-output websocket event."""

    prompt_id: str | None
    node_id: str | None
    list_index: int | None
    cube_id: str
    default_alias: str
    instance_alias: str
    instance_id: str
    media_kind: MediaKind
    value_type: str
    artifacts: tuple[ComfyImageArtifact, ...]
    substitute: "SubstituteVisualIdentity | None" = None
    version: int = 1


@dataclass(frozen=True)
class SubstituteVisualIdentity:
    """Describe Substitute visual routing identity carried by Backend events."""

    workflow_id: str
    generation_run_id: str
    client_id: str
    source_key: str
    source_label: str
    scene_run_id: str | None = None
    scene_key: str | None = None
    scene_title: str | None = None
    scene_order: int | None = None
    scene_count: int | None = None


def parse_cube_output_event(data: Mapping[str, object]) -> CubeOutputEvent | None:
    """Parse a cube-output event payload."""

    version = data.get("version")
    if version not in {1, 2}:
        return None
    cube_id = _required_string(data.get("cube_id"))
    default_alias = _required_string(data.get("default_alias"))
    media_kind = _media_kind(data.get("media_kind"))
    value_type = _required_string(data.get("value_type"))
    artifacts = data.get("artifacts")
    if (
        cube_id is None
        or default_alias is None
        or media_kind is None
        or value_type is None
        or not isinstance(artifacts, list)
    ):
        return None
    parsed_artifacts = tuple(
        artifact
        for artifact in (_parse_artifact(item) for item in artifacts)
        if artifact is not None
    )
    if len(parsed_artifacts) != len(artifacts):
        return None
    return CubeOutputEvent(
        prompt_id=_optional_string(data.get("prompt_id")),
        node_id=_optional_string(data.get("node_id")),
        list_index=_optional_int(data.get("list_index")),
        cube_id=cube_id,
        default_alias=default_alias,
        instance_alias=_optional_string(data.get("instance_alias")) or default_alias,
        instance_id=_optional_string(data.get("instance_id")) or "",
        media_kind=media_kind,
        value_type=value_type,
        artifacts=parsed_artifacts,
        substitute=parse_substitute_visual_identity(data.get("substitute")),
        version=2 if version == 2 else 1,
    )


def _parse_artifact(value: object) -> ComfyImageArtifact | None:
    """Parse one artifact payload."""

    if not isinstance(value, dict):
        return None
    filename = _required_string(value.get("filename"))
    subfolder = _optional_string(value.get("subfolder"))
    artifact_type = _required_string(value.get("type"))
    media_kind = _media_kind(value.get("media_kind"))
    if filename is None or artifact_type is None or media_kind is None:
        return None
    return ComfyImageArtifact(
        filename=filename,
        subfolder=subfolder or "",
        type=artifact_type,
        media_kind=media_kind,
        mime_type=_optional_string(value.get("mime_type")),
        width=_optional_int(value.get("width")),
        height=_optional_int(value.get("height")),
        duration_seconds=_optional_float(value.get("duration_seconds")),
    )


def parse_substitute_visual_identity(
    value: object,
) -> SubstituteVisualIdentity | None:
    """Parse Substitute visual identity from a Backend-enriched payload."""

    if not isinstance(value, Mapping):
        return None
    if value.get("schemaVersion") != 1:
        return None
    workflow_id = _required_string(value.get("workflowId"))
    generation_run_id = _required_string(value.get("generationRunId"))
    client_id = _required_string(value.get("clientId"))
    source_key = _required_string(value.get("sourceKey"))
    source_label = _required_string(value.get("sourceLabel"))
    if (
        workflow_id is None
        or generation_run_id is None
        or client_id is None
        or source_key is None
        or source_label is None
    ):
        return None
    return SubstituteVisualIdentity(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        client_id=client_id,
        source_key=source_key,
        source_label=source_label,
        scene_run_id=_optional_string(value.get("sceneRunId")),
        scene_key=_optional_string(value.get("sceneKey")),
        scene_title=_optional_string(value.get("sceneTitle")),
        scene_order=_optional_int(value.get("sceneOrder")),
        scene_count=_optional_int(value.get("sceneCount")),
    )


def _required_string(value: object) -> str | None:
    """Return a non-empty string payload field."""

    if isinstance(value, str) and value:
        return value
    return None


def _optional_string(value: object) -> str | None:
    """Return an optional string payload field."""

    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return None


def _optional_int(value: object) -> int | None:
    """Return an optional integer payload field."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_float(value: object) -> float | None:
    """Return an optional float payload field."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _media_kind(value: object) -> MediaKind | None:
    """Return a supported media-kind value."""

    if isinstance(value, str) and value in {
        "image",
        "audio",
        "video",
        "value",
        "unknown",
    }:
        return cast(MediaKind, value)
    return None
