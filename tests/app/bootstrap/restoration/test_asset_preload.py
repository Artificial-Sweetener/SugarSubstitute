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
from tests.support.execution import ImmediateTaskSubmitter
from substitute.domain.output_media import OutputMediaKind
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


def test_workspace_restore_asset_preload_prepares_editable_document(
    tmp_path: Path,
) -> None:
    """Restore preloading should expose worker-prepared editable authority."""

    archive_path = tmp_path / "input-editable-document.ccanvas"
    archive_path.write_bytes(b"editable-document")
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"
    input_path.write_bytes(b"input-bytes")
    output_path.write_bytes(b"output-bytes")
    prepared = object()
    prepared_paths: list[Path] = []

    def prepare_document(path: Path) -> object:
        """Record preparation and return its detached authority."""

        prepared_paths.append(path)
        return prepared

    handle = WorkspaceRestoreAssetPreloadHandle(
        _workspace(input_path=input_path, output_path=output_path),
        submitter=ImmediateTaskSubmitter(),
        editable_document_path=archive_path,
        prepare_editable_document=prepare_document,
    )

    handle.start()

    assert prepared_paths == [archive_path]
    assert handle.prepared_editable_document() is prepared


def test_workspace_restore_asset_preload_does_not_buffer_video_files(
    tmp_path: Path,
) -> None:
    """Startup preload should leave large videos to the bounded media probe."""

    input_path = tmp_path / "input.png"
    video_path = tmp_path / "output.webm"
    input_path.write_bytes(b"input-bytes")
    video_path.write_bytes(b"video-bytes")
    handle = WorkspaceRestoreAssetPreloadHandle(
        _workspace(
            input_path=input_path,
            output_path=video_path,
            media_kind=OutputMediaKind.VIDEO,
        ),
        submitter=ImmediateTaskSubmitter(),
    )

    handle.start()

    assert handle.image_bytes(input_path) == b"input-bytes"
    assert handle.image_bytes(video_path) is None


def _workspace(
    *,
    input_path: Path,
    output_path: Path,
    media_kind: OutputMediaKind = OutputMediaKind.IMAGE,
) -> WorkspaceSnapshot:
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
                            media_kind=media_kind,
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
