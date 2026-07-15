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

"""Prepare workspace snapshots for append into an already-open shell."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.workflows import normalize_default_workflow_tab_label
from substitute.domain.workspace_snapshot import WorkflowSnapshot, WorkspaceSnapshot


class WorkspaceAppendService:
    """Own pure workspace snapshot append collision policy."""

    def snapshot_with_unique_open_ids(
        self,
        snapshot: WorkspaceSnapshot,
        *,
        existing_workflow_ids: set[str],
        existing_tab_labels: set[str],
    ) -> WorkspaceSnapshot:
        """Return a copy whose workflow ids and labels do not collide."""

        workflow_id_map: dict[str, str] = {}
        workflows: list[WorkflowSnapshot] = []
        existing_ids = set(existing_workflow_ids)
        existing_labels = set(existing_tab_labels)
        for workflow in snapshot.workflows:
            workflow_id = self.unique_restored_workflow_id(
                workflow.workflow_id,
                existing_ids,
            )
            tab_label = self.unique_restored_workflow_label(
                workflow.tab_label,
                existing_labels,
            )
            existing_ids.add(workflow_id)
            existing_labels.add(tab_label)
            workflow_id_map[workflow.workflow_id] = workflow_id
            workflows.append(
                replace(
                    workflow,
                    workflow_id=workflow_id,
                    tab_label=tab_label,
                )
            )
        return replace(
            snapshot,
            workflows=tuple(workflows),
            tab_order=tuple(
                workflow_id_map[workflow_id]
                for workflow_id in snapshot.tab_order
                if workflow_id in workflow_id_map
            ),
            active_route=workflow_id_map.get(
                snapshot.active_route,
                snapshot.active_route,
            ),
            shell_layout=None,
        )

    @staticmethod
    def unique_restored_workflow_id(
        workflow_id: str,
        existing_ids: set[str],
    ) -> str:
        """Return a workflow id that is not currently open."""

        if workflow_id not in existing_ids:
            return workflow_id
        counter = 2
        while True:
            candidate = f"{workflow_id}-{counter}"
            if candidate not in existing_ids:
                return candidate
            counter += 1

    @staticmethod
    def unique_restored_workflow_label(
        tab_label: str,
        existing_labels: set[str],
    ) -> str:
        """Return a workflow tab label that is not currently open."""

        normalized = normalize_default_workflow_tab_label(tab_label)
        if normalized not in existing_labels:
            return normalized
        counter = 2
        while True:
            candidate = f"{normalized} ({counter})"
            if candidate not in existing_labels:
                return candidate
            counter += 1


__all__ = [
    "WorkspaceAppendService",
]
