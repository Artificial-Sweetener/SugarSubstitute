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

"""Tests for restored workspace image byte preloading."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.workspace_restore_asset_preload import (
    WorkspaceRestoreAssetPreloadHandle,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    ImageMetaSnapshot,
    InputImageReference,
    OutputImageReference,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.domain.workspace_snapshot.models import (
    WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
)


class _CloseRecorder:
    """Record execution submitter close requests."""

    def __init__(self) -> None:
        """Initialize close tracking."""

        self.close_calls = 0

    def close(self) -> None:
        """Record one close request."""

        self.close_calls += 1


def test_workspace_restore_asset_preload_reads_unique_image_bytes(
    tmp_path: Path,
) -> None:
    """Restore asset preload should cache referenced image file bytes."""

    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"
    input_path.write_bytes(b"input-bytes")
    output_path.write_bytes(b"output-bytes")
    close_recorder = _CloseRecorder()
    handle = WorkspaceRestoreAssetPreloadHandle(
        _workspace(input_path=input_path, output_path=output_path),
        submitter=ImmediateTaskSubmitter(),
        close_submitter=close_recorder.close,
    )

    handle.start()
    handle.start()
    handle.shutdown()

    assert handle.image_bytes(input_path) == b"input-bytes"
    assert handle.image_bytes(output_path) == b"output-bytes"
    assert handle.image_bytes(tmp_path / "missing.png") is None
    assert close_recorder.close_calls == 1


def _workspace(*, input_path: Path, output_path: Path) -> WorkspaceSnapshot:
    """Build a workspace with input and output image references."""

    return WorkspaceSnapshot(
        schema_version=WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
        workflows=(
            WorkflowSnapshot(
                workflow_id="wf-a",
                tab_label="Workflow",
                workflow=WorkflowState(),
                input_images=(
                    InputImageReference(
                        image_id="input",
                        path=input_path,
                        sequence=0,
                    ),
                ),
                output_images=(
                    OutputImageReference(
                        image_id="output",
                        path=output_path,
                        metadata=ImageMetaSnapshot(
                            workflow_name="Workflow",
                            cube_name="Save",
                            image_number=1,
                            suffix="",
                            path=output_path,
                        ),
                        sequence=0,
                    ),
                ),
            ),
        ),
        tab_order=("wf-a",),
        active_route="wf-a",
        active_workflow_id="wf-a",
        shell_layout=None,
    )
