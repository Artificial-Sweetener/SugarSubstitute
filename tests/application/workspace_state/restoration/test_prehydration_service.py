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

"""Tests for safe pre-show workspace prehydration."""

from __future__ import annotations

from pathlib import Path

from substitute.application.workspace_state import WorkspacePrehydrationService
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    ImageMetaSnapshot,
    InputImageReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


class _Port:
    """Record prehydration port calls without projecting editor surfaces."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.calls: list[tuple[str, object]] = []
        self.restored_inputs: list[str] = []
        self.restored_outputs: list[tuple[str, str]] = []
        self.shell_layout: ShellLayoutSnapshot | None = None

    def begin_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Record prehydration start."""

        self.calls.append(("begin", snapshot.active_route))

    def reset_restored_workspace(self) -> None:
        """Record workspace reset."""

        self.calls.append(("reset", ""))

    def add_prehydrated_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Record one prehydrated workflow."""

        self.calls.append(("workflow", (snapshot.workflow_id, activate)))

    def load_restored_input_image(self, path: Path) -> object | None:
        """Return a deterministic input payload for existing paths."""

        self.calls.append(("load_input", path))
        return object()

    def restore_input_image(
        self,
        reference: InputImageReference,
        image: object,
    ) -> None:
        """Record one restored input image."""

        assert image is not None
        self.restored_inputs.append(reference.image_id)

    def restore_input_mask(self, _reference: object) -> bool:
        """Report unavailable mask restore to match current shell behavior."""

        return False

    def load_restored_output_image(self, path: Path) -> object | None:
        """Return a deterministic output payload for existing paths."""

        self.calls.append(("load_output", path))
        return object()

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: object,
    ) -> None:
        """Record one restored output image."""

        assert image is not None
        assert image_meta is not None
        self.restored_outputs.append((workflow_id, reference.image_id))

    def remember_prehydrated_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Record remembered shell layout."""

        self.shell_layout = snapshot
        self.calls.append(("layout", snapshot is not None))

    def finish_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Record prehydration completion."""

        self.calls.append(("finish", snapshot.active_workflow_id))


def test_workspace_prehydration_adds_tabs_and_assets_without_projection() -> None:
    """Prehydration should restore safe chrome and local assets in tab order."""

    shell_layout = ShellLayoutSnapshot(main_splitter_sizes=(300, 900))
    workspace = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            _workflow("wf-a"),
            _workflow(
                "wf-b",
                input_images=(
                    InputImageReference(
                        image_id="input-b",
                        path=Path("input.png"),
                        sequence=0,
                    ),
                ),
                output_images=(
                    OutputImageReference(
                        image_id="output-b",
                        path=Path("output.png"),
                        metadata=ImageMetaSnapshot(
                            workflow_name="Workflow",
                            cube_name="Save",
                            image_number=1,
                            suffix="",
                            path=Path("output.png"),
                        ),
                        sequence=0,
                    ),
                ),
            ),
        ),
        tab_order=("wf-b", "wf-a"),
        active_route="wf-b",
        active_workflow_id="wf-b",
        shell_layout=shell_layout,
    )
    port = _Port()

    result = WorkspacePrehydrationService().prehydrate(workspace, port)

    assert result.warnings == ()
    assert ("workflow", ("wf-b", True)) in port.calls
    assert ("workflow", ("wf-a", False)) in port.calls
    assert port.restored_inputs == ["input-b"]
    assert port.restored_outputs == [("wf-b", "output-b")]
    assert port.shell_layout == shell_layout
    assert ("finish", "wf-b") in port.calls


def test_workspace_prehydration_reports_missing_tab_order_entries() -> None:
    """Prehydration should repair stale tab ids without failing restore."""

    workspace = WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(_workflow("wf-a"),),
        tab_order=("missing", "wf-a"),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=None,
    )

    result = WorkspacePrehydrationService().prehydrate(workspace, _Port())

    assert result.warnings == ("Skipped missing workflow missing.",)


def _workflow(
    workflow_id: str,
    *,
    input_images: tuple[InputImageReference, ...] = (),
    output_images: tuple[OutputImageReference, ...] = (),
) -> WorkflowSnapshot:
    """Build one workflow snapshot for prehydration tests."""

    return WorkflowSnapshot(
        workflow_id=workflow_id,
        tab_label=workflow_id,
        workflow=WorkflowState(),
        input_images=input_images,
        output_images=output_images,
    )
