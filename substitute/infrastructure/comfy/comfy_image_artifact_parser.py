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

"""Parse canonical image artifact references from Comfy output payloads."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact


def parse_comfy_image_artifacts(
    output: object,
) -> tuple[ComfyImageArtifact, ...] | None:
    """Return image artifacts, or ``None`` when their envelope is malformed."""

    if output is None:
        return ()
    if not isinstance(output, Mapping):
        return None
    raw_images = output.get("images")
    if raw_images is None:
        return ()
    if not isinstance(raw_images, list):
        return None
    artifacts: list[ComfyImageArtifact] = []
    for raw_image in raw_images:
        if not isinstance(raw_image, Mapping):
            return None
        filename = raw_image.get("filename")
        artifact_type = raw_image.get("type")
        subfolder = raw_image.get("subfolder", "")
        if (
            not isinstance(filename, str)
            or not filename
            or not isinstance(artifact_type, str)
            or not artifact_type
            or not isinstance(subfolder, str)
        ):
            return None
        artifacts.append(
            ComfyImageArtifact(
                filename=filename,
                subfolder=subfolder,
                type=artifact_type,
            )
        )
    return tuple(artifacts)


__all__ = ["parse_comfy_image_artifacts"]
