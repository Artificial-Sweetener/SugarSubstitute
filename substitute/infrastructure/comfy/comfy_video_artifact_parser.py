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

"""Parse generated video artifact references from Comfy output payloads."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact

_VIDEO_COLLECTION_KEYS = ("videos", "gifs")


def parse_comfy_video_artifacts(
    output: object,
) -> tuple[ComfyImageArtifact, ...] | None:
    """Return video artifacts, or ``None`` for a malformed video envelope."""

    if output is None:
        return ()
    if not isinstance(output, Mapping):
        return None
    raw_artifacts = _video_collection(output)
    if raw_artifacts is None:
        return ()
    if not isinstance(raw_artifacts, list):
        return None
    artifacts: list[ComfyImageArtifact] = []
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, Mapping):
            return None
        filename = raw_artifact.get("filename")
        artifact_type = raw_artifact.get("type")
        subfolder = raw_artifact.get("subfolder", "")
        if (
            not isinstance(filename, str)
            or not filename
            or not isinstance(artifact_type, str)
            or not artifact_type
            or not isinstance(subfolder, str)
        ):
            return None
        format_value = raw_artifact.get("format")
        artifacts.append(
            ComfyImageArtifact(
                filename=filename,
                subfolder=subfolder,
                type=artifact_type,
                media_kind="video",
                mime_type=(
                    format_value
                    if isinstance(format_value, str)
                    and format_value.startswith("video/")
                    else None
                ),
                width=_positive_int(raw_artifact.get("width")),
                height=_positive_int(raw_artifact.get("height")),
                duration_seconds=_positive_float(raw_artifact.get("duration_seconds")),
            )
        )
    return tuple(artifacts)


def _video_collection(output: Mapping[str, object]) -> object | None:
    """Resolve generic, VHS, and core animated history collection shapes."""

    for key in _VIDEO_COLLECTION_KEYS:
        if key in output:
            return output[key]
    if output.get("animated") is True:
        return output.get("images")
    video = output.get("video")
    if isinstance(video, Mapping):
        return [video]
    return None


def _positive_int(value: object) -> int | None:
    """Return a positive non-boolean integer."""

    return value if type(value) is int and value > 0 else None


def _positive_float(value: object) -> float | None:
    """Return a positive duration as float."""

    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return float(value)


__all__ = ["parse_comfy_video_artifacts"]
