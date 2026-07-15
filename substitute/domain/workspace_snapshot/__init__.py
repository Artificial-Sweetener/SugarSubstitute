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

"""Expose Qt-free workspace snapshot models and codecs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from substitute.domain.workspace_snapshot.models import (
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

if TYPE_CHECKING:
    from substitute.domain.workspace_snapshot.codecs import (
        SnapshotCodecError,
        workflow_state_from_json,
        workflow_state_to_json,
        workspace_snapshot_from_json,
        workspace_snapshot_to_json,
    )

_CODEC_EXPORTS = {
    "SnapshotCodecError",
    "workflow_state_from_json",
    "workflow_state_to_json",
    "workspace_snapshot_from_json",
    "workspace_snapshot_to_json",
}


def __getattr__(name: str) -> Any:
    """Load codec exports only when callers request them."""

    if name not in _CODEC_EXPORTS:
        raise AttributeError(name)
    from substitute.domain.workspace_snapshot import codecs

    value = getattr(codecs, name)
    globals()[name] = value
    return value


__all__ = [
    "EditorViewportSnapshot",
    "CanvasLayoutSnapshot",
    "FloatingCanvasWindowSnapshot",
    "ImageMetaSnapshot",
    "InputImageReference",
    "InputMaskReference",
    "OutputImageReference",
    "ShellLayoutSnapshot",
    "SnapshotCodecError",
    "WindowGeometrySnapshot",
    "WorkflowSnapshot",
    "WorkspaceSnapshot",
    "workflow_state_from_json",
    "workflow_state_to_json",
    "workspace_snapshot_from_json",
    "workspace_snapshot_to_json",
]
