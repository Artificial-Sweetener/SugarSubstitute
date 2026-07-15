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

"""Contract tests for workflow-tab reorder preview math."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect

from substitute.presentation.workflows.workflow_tab_reorder_controller import (
    WorkflowTabReorderController,
)


class _Geometry:
    """Provide deterministic workflow-tab geometry for reorder tests."""

    def __init__(self, workflow_ids: list[str]) -> None:
        """Create evenly spaced tab slots for workflow ids."""

        self._workflow_ids = workflow_ids

    def workflow_ids_in_order(self) -> list[str]:
        """Return committed workflow ids."""

        return list(self._workflow_ids)

    def workflow_tab_rect_by_id(self, workflow_id: str) -> QRect | None:
        """Return a simple tab rectangle for one workflow id."""

        try:
            index = self._workflow_ids.index(workflow_id)
        except ValueError:
            return None
        return QRect(index * 100, 0, 80, 32)


def test_preview_returns_transient_order_without_mutating_committed_order() -> None:
    """Preview math should move the dragged id without changing source order."""

    geometry = _Geometry(["wf-a", "wf-b", "wf-c"])
    controller = WorkflowTabReorderController(geometry)

    preview = controller.preview(
        workflow_id="wf-b",
        origin_index=1,
        pointer_pos=QPoint(10, 0),
    )

    assert geometry.workflow_ids_in_order() == ["wf-a", "wf-b", "wf-c"]
    assert preview.target_index == 0
    assert preview.preview_order == ("wf-b", "wf-a", "wf-c")


def test_preview_order_returns_committed_order_for_missing_workflow() -> None:
    """Invalid preview inputs should fail closed to committed order."""

    geometry = _Geometry(["wf-a", "wf-b", "wf-c"])
    controller = WorkflowTabReorderController(geometry)

    preview_order = controller.preview_order(
        workflow_id="missing",
        target_index=0,
    )

    assert preview_order == ("wf-a", "wf-b", "wf-c")


def test_finish_returns_commit_order_for_completed_drag() -> None:
    """Release should return the same preview order used for final commit."""

    geometry = _Geometry(["wf-a", "wf-b", "wf-c"])
    controller = WorkflowTabReorderController(geometry)

    command = controller.finish(
        workflow_id="wf-c",
        origin_index=2,
        pointer_pos=QPoint(10, 0),
    )

    assert command is not None
    assert command.workflow_id == "wf-c"
    assert command.target_index == 0
    assert command.preview_order == ("wf-c", "wf-a", "wf-b")
