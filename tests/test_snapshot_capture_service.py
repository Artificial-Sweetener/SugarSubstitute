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

"""Tests for session snapshot capture orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from substitute.application.workspace_state import SnapshotCaptureService
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
)


class _CapturePort:
    """Expose deterministic live state for capture tests."""

    def __init__(self) -> None:
        """Initialize a two-workflow capture surface."""

        self.first = WorkflowState()
        self.second = WorkflowState()

    def workflow_ids_in_order(self) -> tuple[str, ...]:
        """Return tab order."""

        return ("wf-1", "missing", "wf-2")

    def active_workspace_route(self) -> str:
        """Return active route."""

        return "settings"

    def active_workflow_id(self) -> str:
        """Return the workflow active beneath the current route."""

        return "wf-2"

    def workflow_state(self, workflow_id: str) -> WorkflowState | None:
        """Return workflow states for known ids."""

        return {"wf-1": self.first, "wf-2": self.second}.get(workflow_id)

    def workflow_tab_label(self, workflow_id: str) -> str:
        """Return workflow labels."""

        return {"wf-1": "One", "wf-2": "Two"}[workflow_id]

    def active_cube_alias(self, workflow_id: str) -> str | None:
        """Return active cube aliases."""

        return {"wf-1": None, "wf-2": "Sampler"}[workflow_id]

    def input_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputImageReference, ...]:
        """Return deterministic input images."""

        del workflow
        return (
            InputImageReference(
                image_id=f"input-{workflow_id}",
                path=Path("input.png"),
                sequence=1,
            ),
        )

    def input_mask_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[InputMaskReference, ...]:
        """Return no masks for this capture test."""

        del workflow_id, workflow
        return ()

    def output_image_references(
        self,
        workflow_id: str,
        workflow: WorkflowState,
    ) -> tuple[OutputImageReference, ...]:
        """Return deterministic output images."""

        del workflow
        return (
            OutputImageReference(
                image_id=str(UUID("33333333-3333-3333-3333-333333333333")),
                path=Path("output.png"),
                metadata=ImageMetaSnapshot(
                    workflow_name=workflow_id,
                    cube_name="Save",
                    image_number=1,
                    suffix="",
                    path=Path("output.png"),
                ),
                sequence=1,
            ),
        )

    def editor_viewport_snapshot(
        self,
        workflow_id: str,
    ) -> EditorViewportSnapshot | None:
        """Return deterministic editor viewport state."""

        if workflow_id == "wf-2":
            return EditorViewportSnapshot(
                scroll_value=240,
                scroll_maximum=1000,
                anchor_cube_alias="Sampler",
            )
        return None

    def shell_layout_snapshot(self) -> ShellLayoutSnapshot | None:
        """Return layout snapshot."""

        return ShellLayoutSnapshot(maximized=True)


def test_snapshot_capture_service_captures_ordered_workflows_and_layout() -> None:
    """Capture service should skip missing workflow ids and preserve route/layout."""

    captured_at = datetime(2026, 5, 8, 12, tzinfo=timezone.utc)
    snapshot = SnapshotCaptureService(clock=lambda: captured_at).capture(_CapturePort())

    assert snapshot.captured_at == captured_at
    assert snapshot.workspace.tab_order == ("wf-1", "wf-2")
    assert snapshot.workspace.active_route == "settings"
    assert snapshot.workspace.active_workflow_id == "wf-2"
    assert [workflow.tab_label for workflow in snapshot.workspace.workflows] == [
        "One",
        "Two",
    ]
    assert snapshot.workspace.workflows[1].active_cube_alias == "Sampler"
    assert snapshot.workspace.workflows[0].editor_viewport is None
    assert snapshot.workspace.workflows[1].editor_viewport == EditorViewportSnapshot(
        scroll_value=240,
        scroll_maximum=1000,
        anchor_cube_alias="Sampler",
    )
    assert snapshot.workspace.workflows[0].input_images[0].image_id == "input-wf-1"
    assert snapshot.workspace.workflows[0].output_images[0].path == Path("output.png")
    assert snapshot.workspace.shell_layout is not None
    assert snapshot.workspace.shell_layout.maximized is True


def test_snapshot_capture_success_is_quiet_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Routine snapshot capture success should stay out of INFO logs."""

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.application.workspace_state.snapshot_capture_service",
    )

    SnapshotCaptureService().capture(_CapturePort())

    assert caplog.records == []
