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

"""Contract tests for output canvas projection scheduling."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
    ProjectionReason,
)


def test_scheduler_coalesces_generated_output_projection_until_flush() -> None:
    """Generated output projection should use latest request wins."""

    _app()
    calls: list[tuple[str, object]] = []
    visible = True

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: visible,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.GENERATED_OUTPUT)
    scheduler.request_projection("wf", reason=ProjectionReason.GENERATED_OUTPUT)
    scheduler.flush()

    assert calls == [("wf", None)]


def test_scheduler_generated_output_projection_uses_latest_registered_image() -> None:
    """Generated output projection should replace stale image identifiers."""

    _app()
    calls: list[tuple[str, object]] = []
    first_image_id = uuid4()
    second_image_id = uuid4()

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
    )

    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=first_image_id,
    )
    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=second_image_id,
    )
    scheduler.flush()

    assert calls == [("wf", second_image_id)]


def test_scheduler_marks_output_activity_after_generated_projection_flush() -> None:
    """Generated canvas projection should mark recent output activity after work lands."""

    _app()
    calls: list[tuple[str, object]] = []
    marked_reasons: list[str] = []

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
        output_activity_marker=marked_reasons.append,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.GENERATED_OUTPUT)
    scheduler.flush()

    assert calls == [("wf", None)]
    assert marked_reasons == ["generated_canvas_projection_flush"]


def test_scheduler_uses_prompt_interval_while_prompt_interaction_is_active() -> None:
    """Generated output projection should use a wider interaction frame budget."""

    _app()
    calls: list[tuple[str, object]] = []

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
        interval_ms=5,
        active_prompt_interval_ms=33,
        prompt_interaction_active=lambda: True,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.GENERATED_OUTPUT)

    assert scheduler._timer.interval() == 33
    assert calls == []


def test_scheduler_projects_user_selection_immediately() -> None:
    """Explicit user output selection should bypass generated-output delay."""

    _app()
    calls: list[tuple[str, object]] = []
    marked_reasons: list[str] = []

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: False,
        output_activity_marker=marked_reasons.append,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.USER_SELECTED_OUTPUT)

    assert calls == [("wf", None)]
    assert marked_reasons == ["canvas_projection_user_selected_output"]


def test_scheduler_defers_workflow_activation_until_flush() -> None:
    """Workflow activation should coalesce through the projection flush timer."""

    _app()
    calls: list[tuple[str, object]] = []
    marked_reasons: list[str] = []

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
        output_activity_marker=marked_reasons.append,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.WORKFLOW_ACTIVATED)

    assert calls == []

    scheduler.flush()

    assert calls == [("wf", None)]
    assert marked_reasons == ["canvas_projection_workflow_activated_flush"]


def test_scheduler_generated_projection_preempts_deferred_activation() -> None:
    """A generated output id should survive a later route activation flush."""

    _app()
    calls: list[tuple[str, object]] = []
    generated_image_id = uuid4()

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
    )

    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=generated_image_id,
    )
    scheduler.request_projection("wf", reason=ProjectionReason.WORKFLOW_ACTIVATED)
    scheduler.flush()

    assert calls == [("wf", generated_image_id)]


def test_scheduler_user_selection_clears_pending_generated_projection() -> None:
    """Explicit user selection should preempt pending generated projection."""

    _app()
    calls: list[tuple[str, object]] = []
    generated_image_id = uuid4()
    selected_image_id = uuid4()

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
    )

    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=generated_image_id,
    )
    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.USER_SELECTED_OUTPUT,
        registered_image_id=selected_image_id,
    )
    scheduler.flush()

    assert calls == [("wf", selected_image_id)]


def test_scheduler_user_selection_clears_pending_deferred_projection() -> None:
    """Explicit user selection should preempt pending route projection."""

    _app()
    calls: list[tuple[str, object]] = []
    selected_image_id = uuid4()

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: True,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.WORKFLOW_ACTIVATED)
    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.USER_SELECTED_OUTPUT,
        registered_image_id=selected_image_id,
    )
    scheduler.flush()

    assert calls == [("wf", selected_image_id)]


def test_scheduler_defers_hidden_generated_projection_until_visible() -> None:
    """Generated projection should wait when the output canvas is hidden."""

    _app()
    calls: list[tuple[str, object]] = []
    visible = False

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: visible,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.GENERATED_OUTPUT)
    scheduler.flush()

    assert calls == []

    visible = True
    scheduler.flush()

    assert calls == [("wf", None)]


def test_scheduler_discards_pending_work_for_removed_workflow() -> None:
    """Workflow removal should drop generated and deferred projection work."""

    _app()
    calls: list[tuple[str, object]] = []
    visible = False

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf",
        output_canvas_visible=lambda: visible,
    )

    scheduler.request_projection("wf", reason=ProjectionReason.GENERATED_OUTPUT)
    scheduler.request_projection("wf", reason=ProjectionReason.WORKFLOW_ACTIVATED)
    scheduler.discard_workflow("wf")
    visible = True
    scheduler.flush()

    assert calls == []


def test_scheduler_rekeys_pending_work_for_renamed_workflow() -> None:
    """Workflow rename should move pending projections to the new workflow ID."""

    _app()
    calls: list[tuple[str, object]] = []
    visible = False
    image_id = uuid4()

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: "wf-renamed",
        output_canvas_visible=lambda: visible,
    )

    scheduler.request_projection(
        "wf",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=image_id,
    )
    scheduler.rename_workflow("wf", "wf-renamed")
    visible = True
    scheduler.flush()

    assert calls == [("wf-renamed", image_id)]


def test_scheduler_preserves_inactive_workflow_request_until_return() -> None:
    """Switching workflows before flush should retain each workflow's request."""

    _app()
    calls: list[tuple[str, object]] = []
    active_workflow = "first"
    first_image_id = uuid4()
    second_image_id = uuid4()

    def project(workflow_id: str, image_id: object = None) -> None:
        calls.append((workflow_id, image_id))

    scheduler = CanvasProjectionScheduler(
        project_workflow=project,
        active_workflow_id=lambda: active_workflow,
        output_canvas_visible=lambda: True,
    )
    scheduler.request_projection(
        "first",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=first_image_id,
    )

    active_workflow = "second"
    scheduler.request_projection(
        "second",
        reason=ProjectionReason.GENERATED_OUTPUT,
        registered_image_id=second_image_id,
    )
    scheduler.flush()

    assert calls == [("second", second_image_id)]

    active_workflow = "first"
    scheduler.flush()

    assert calls == [("second", second_image_id), ("first", first_image_id)]


def _app() -> QApplication:
    """Return a QApplication for QTimer-backed scheduler tests."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
