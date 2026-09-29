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

"""Validate untrusted Comfy artifact locator fields."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from substitute.infrastructure.comfy.image_artifact import ComfyImageArtifact

_ALLOWED_ARTIFACT_TYPES = frozenset({"input", "output", "temp"})


def validate_artifact_locator(artifact: ComfyImageArtifact) -> None:
    """Reject artifact fields that are unsafe to send to Comfy's view endpoint."""

    if artifact.type not in _ALLOWED_ARTIFACT_TYPES:
        raise ValueError(f"Unsupported Comfy artifact type: {artifact.type!r}")
    if not _is_leaf_name(artifact.filename):
        raise ValueError("Comfy artifact filename must be a relative leaf name.")
    if not _is_relative_subfolder(artifact.subfolder):
        raise ValueError("Comfy artifact subfolder must be a safe relative path.")


def _is_leaf_name(value: str) -> bool:
    """Return whether text is a non-special filename without path syntax."""

    return bool(
        value
        and value not in {".", ".."}
        and PurePosixPath(value).name == value
        and PureWindowsPath(value).name == value
        and not PureWindowsPath(value).is_reserved()
        and ":" not in value
        and "\x00" not in value
    )


def _is_relative_subfolder(value: str) -> bool:
    """Return whether a Comfy subfolder is relative and traversal-free."""

    if "\x00" in value or ":" in value:
        return False
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and all(
        part not in {"", ".", ".."} for part in path.parts
    )


__all__ = ["validate_artifact_locator"]
