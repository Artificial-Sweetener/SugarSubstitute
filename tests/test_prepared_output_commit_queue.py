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

"""Contract tests for bounded prepared output commits."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from substitute.application.workflows.output_canvas_state_service import (
    OutputFocusMutationResult,
    OutputFocusSnapshot,
    OutputImageRegistrationResult,
    OutputProjectionSchedulingIntent,
)
from substitute.domain.workflow import OutputFocusMode
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.output_image_commit_queue import (
    PreparedOutputCommitQueue,
)


def test_commit_queue_commits_one_prepared_output_per_tick() -> None:
    """Prepared output commits should be FIFO and bounded per drain tick."""

    _app()
    committed: list[str] = []
    projected: list[tuple[str, object]] = []
    marked_reasons: list[str] = []

    def project(workflow_id: str, image_id: object = None) -> None:
        projected.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
    )

    def commit(prepared: PreparedOutputImage) -> OutputImageRegistrationResult:
        committed.append(prepared.request.node_id)
        image_id = uuid4()
        return _registration_result(
            workflow_id=prepared.request.workflow_id,
            image_id=image_id,
            should_schedule=True,
        )

    queue = PreparedOutputCommitQueue(
        commit_prepared=commit,
        handle_failure=lambda _failure: None,
        projection_scheduler=scheduler,
        batch_size=1,
        output_activity_marker=marked_reasons.append,
    )

    queue.enqueue_prepared(_prepared("first"))
    queue.enqueue_prepared(_prepared("second"))
    queue.drain_once()

    assert committed == ["first"]
    assert queue.pending_count() == 1
    assert marked_reasons == ["output_commit_queue_drain"]

    queue.drain_once()

    assert committed == ["first", "second"]
    assert marked_reasons == [
        "output_commit_queue_drain",
        "output_commit_queue_drain",
    ]


def _prepared(node_id: str) -> PreparedOutputImage:
    """Return a prepared output DTO for commit queue tests."""

    return PreparedOutputImage(
        request=OutputImageCommitRequest(
            workflow_id="wf",
            file_path=Path(f"E:/{node_id}.png"),
            node_id=node_id,
            node_meta_title="Cube.Output",
            workflow_name="Workflow",
            source_key=f"wf:{node_id}",
            source_label=node_id,
        ),
        image=QImage(8, 8, QImage.Format.Format_ARGB32),
    )


def _app() -> QApplication:
    """Return a QApplication for QTimer-backed queue tests."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _registration_result(
    *,
    workflow_id: str,
    image_id: UUID,
    should_schedule: bool,
) -> OutputImageRegistrationResult:
    """Return a registered Output result for commit queue tests."""

    snapshot = OutputFocusSnapshot(
        active_uuid=None,
        set_index=1,
        source_key=None,
        scene_key=None,
        scene_overview=False,
        focus_mode=OutputFocusMode.AUTOMATIC,
    )
    return OutputImageRegistrationResult(
        workflow_id=workflow_id,
        image_id=image_id,
        registered=True,
        focus_change=OutputFocusMutationResult(before=snapshot, after=snapshot),
        preview_close_identity=None,
        projection_intent=OutputProjectionSchedulingIntent(
            workflow_id=workflow_id,
            registered_image_id=image_id,
            should_schedule=should_schedule,
        ),
    )
