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

"""Serialize process-local closed workflow snapshots."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import cast

from substitute.domain.common import JsonObject
from substitute.domain.workspace_snapshot import (
    SnapshotCodecError,
    WorkflowSnapshot,
    WorkspaceSnapshot,
    workspace_snapshot_from_json,
    workspace_snapshot_to_json,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


class ClosedWorkflowSnapshotError(ValueError):
    """Report invalid process-local closed workflow snapshot payloads."""


class ClosedWorkflowSnapshotService:
    """Serialize workflow snapshots for process-local reopen support."""

    def encode(self, snapshot: WorkflowSnapshot) -> bytes:
        """Return compact UTF-8 JSON bytes for one workflow snapshot."""

        workspace = WorkspaceSnapshot(
            schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
            workflows=(snapshot,),
            tab_order=(snapshot.workflow_id,),
            active_route=snapshot.workflow_id,
            active_workflow_id=snapshot.workflow_id,
        )
        payload = workspace_snapshot_to_json(workspace)
        try:
            return json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ClosedWorkflowSnapshotError(
                "Closed workflow snapshot could not be encoded."
            ) from error

    def decode(self, payload: bytes) -> WorkflowSnapshot:
        """Return one workflow snapshot from compact UTF-8 JSON bytes."""

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ClosedWorkflowSnapshotError(
                "Closed workflow snapshot payload is not valid JSON."
            ) from error
        if not isinstance(decoded, dict):
            raise ClosedWorkflowSnapshotError(
                "Closed workflow snapshot payload must be a JSON object."
            )
        try:
            workspace = workspace_snapshot_from_json(cast(JsonObject, decoded))
        except (SnapshotCodecError, TypeError, ValueError) as error:
            raise ClosedWorkflowSnapshotError(
                "Closed workflow snapshot payload is invalid."
            ) from error
        if len(workspace.workflows) != 1:
            raise ClosedWorkflowSnapshotError(
                "Closed workflow snapshot payload must contain exactly one workflow."
            )
        return workspace.workflows[0]

    def rekey_snapshot(
        self,
        snapshot: WorkflowSnapshot,
        *,
        new_workflow_id: str,
    ) -> WorkflowSnapshot:
        """Return snapshot with workflow id replaced for session registration."""

        if not new_workflow_id:
            raise ClosedWorkflowSnapshotError("Reopened workflow id cannot be empty.")
        return replace(snapshot, workflow_id=new_workflow_id)


__all__ = [
    "ClosedWorkflowSnapshotError",
    "ClosedWorkflowSnapshotService",
]
