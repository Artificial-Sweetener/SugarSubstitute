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

"""Verify mounted queue-row reconciliation and pending drag interaction."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from shiboken6 import isValid

from substitute.presentation.generation.queue_list_view import (
    QueueJobInteractionRole,
    QueueJobRowAction,
    QueueJobRowView,
    QueueJobVisualRole,
)
from substitute.presentation.generation.queue_rows_view import GenerationQueueRowsView
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


def _row(
    job_id: str,
    *,
    subtitle: str = "Next",
    status: str = "Pending",
    action: QueueJobRowAction | None = "cancel",
    visual_role: QueueJobVisualRole = "pending",
    interaction_role: QueueJobInteractionRole = "draggable",
    visual_index: int | None = 0,
    dispatch_index: int | None = 0,
) -> QueueJobRowView:
    """Build one queue row with explicit placement identity."""

    return QueueJobRowView(
        job_id=job_id,
        title=f"Workflow {job_id}",
        subtitle=subtitle,
        status=status,
        action=action,
        visual_role=visual_role,
        interaction_role=interaction_role,
        pending_visual_index=visual_index,
        pending_dispatch_index=dispatch_index,
    )


def test_rows_view_reuses_widget_for_content_updates() -> None:
    """Progress changes must update one mounted row without widget replacement."""

    view = GenerationQueueRowsView(surface_mode="panel")
    original = _row(
        "a",
        subtitle="Running",
        status="Running",
        visual_role="active",
        interaction_role="none",
        visual_index=None,
        dispatch_index=None,
    )
    updated = _row(
        "a",
        subtitle="62% complete",
        status="Running",
        visual_role="active",
        interaction_role="none",
        visual_index=None,
        dispatch_index=None,
    )
    try:
        view.set_rows((original,))
        widget = view._row_widgets_by_job_id["a"]
        assert view.update_row(updated)
        assert view._row_widgets_by_job_id["a"] is widget
        assert widget._full_subtitle == "62% complete"
        assert view._layout.indexOf(widget) == 0
    finally:
        destroy_qt_object(view)


def test_rows_view_rejects_incremental_placement_change() -> None:
    """A reorder must use full reconciliation rather than content-only update."""

    view = GenerationQueueRowsView(surface_mode="panel")
    original = _row("a")
    moved = _row("a", visual_index=1, dispatch_index=1)
    try:
        view.set_rows((original,))
        widget = view._row_widgets_by_job_id["a"]
        assert not view.update_row(moved)
        assert view._row_widgets_by_job_id["a"] is widget
        assert view._rows == (original,)
    finally:
        destroy_qt_object(view)


def test_rows_view_deletes_only_removed_job_widgets() -> None:
    """Structural reconciliation must preserve survivors and retire removed rows."""

    view = GenerationQueueRowsView(surface_mode="panel")
    try:
        view.set_rows((_row("a", visual_index=0), _row("b", visual_index=1)))
        first = view._row_widgets_by_job_id["a"]
        removed = view._row_widgets_by_job_id["b"]
        view.set_rows((_row("a", subtitle="Waiting", visual_index=0),))
        assert view._row_widgets_by_job_id["a"] is first
        assert "b" not in view._row_widgets_by_job_id
        assert isValid(removed)
    finally:
        destroy_qt_object(view)
    assert not isValid(removed)


def test_rows_view_pending_drag_emits_dispatch_target() -> None:
    """Dragging a pending visual row must emit the service dispatch insertion."""

    view = GenerationQueueRowsView(surface_mode="panel")
    rows = (
        _row("b", subtitle="Waiting", visual_index=0, dispatch_index=1),
        _row("a", visual_index=1, dispatch_index=0),
    )
    spy = QSignalSpy(view.moveRequested)
    try:
        view.resize(360, 180)
        view.set_rows(rows)
        view.show()
        wait_for_queued_qt_turn()
        source = view._row_widgets_by_job_id["a"]
        start = source.mapToParent(QPoint(12, max(1, source.height() // 2)))
        target = QPoint(12, 0)

        view._handle_body_pressed("a", start)
        view._handle_body_moved("a", target)
        assert view._drop_placeholder is not None
        assert view._drag_proxy is not None
        view._handle_body_released("a", target)

        assert spy.count() == 1
        assert spy.at(0) == ["a", 1]
        assert view._drag_state is None
        assert view._drop_placeholder is None
        assert view._drag_proxy is None
    finally:
        destroy_qt_object(view)


def test_rows_view_ignores_non_pending_drag_attempts() -> None:
    """Active and resolved rows must never acquire pending drag state."""

    view = GenerationQueueRowsView(surface_mode="panel")
    rows = (
        _row(
            "active",
            status="Running",
            visual_role="active",
            interaction_role="none",
            visual_index=None,
            dispatch_index=None,
        ),
        _row(
            "done",
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
            visual_index=None,
            dispatch_index=None,
        ),
    )
    spy = QSignalSpy(view.moveRequested)
    try:
        view.set_rows(rows)
        for job_id in ("active", "done"):
            view._handle_body_pressed(job_id, QPoint(12, 12))
            view._handle_body_moved(job_id, QPoint(12, -30))
            view._handle_body_released(job_id, QPoint(12, -30))
        assert spy.count() == 0
        assert view._drag_state is None
        assert view._drop_placeholder is None
    finally:
        destroy_qt_object(view)


def test_rows_view_placeholder_opens_gap_before_non_pending_rows() -> None:
    """A trailing pending drop slot must remain above active and resolved rows."""

    view = GenerationQueueRowsView(surface_mode="panel")
    rows = (
        _row("pending", visual_index=0, dispatch_index=0),
        _row(
            "active",
            status="Running",
            visual_role="active",
            interaction_role="none",
            visual_index=None,
            dispatch_index=None,
        ),
        _row(
            "done",
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
            visual_index=None,
            dispatch_index=None,
        ),
    )
    try:
        view.resize(360, 220)
        view.set_rows(rows)
        view.show()
        wait_for_queued_qt_turn()
        view._handle_body_pressed("pending", QPoint(12, 10))
        view._handle_body_moved("pending", QPoint(12, 100))
        placeholder = view._drop_placeholder
        assert placeholder is not None
        assert placeholder.height() == view._row_widgets_by_job_id["pending"].height()
        assert view._layout.indexOf(placeholder) < view._layout.indexOf(
            view._row_widgets_by_job_id["active"]
        )
        assert view._layout.indexOf(placeholder) < view._layout.indexOf(
            view._row_widgets_by_job_id["done"]
        )
    finally:
        destroy_qt_object(view)


def test_rows_view_real_action_button_does_not_prime_drag() -> None:
    """The cancel control must remain an action boundary, not a row-body drag target."""

    view = GenerationQueueRowsView(surface_mode="panel")
    spy = QSignalSpy(view.cancelRequested)
    try:
        view.resize(360, 100)
        view.set_rows((_row("a"),))
        view.show()
        wait_for_queued_qt_turn()
        action_button = view._row_widgets_by_job_id["a"]._action_button
        QTest.mouseClick(action_button, Qt.MouseButton.LeftButton)
        assert spy.count() == 1
        assert spy.at(0) == ["a"]
        assert view._drag_state is None
        assert view._drop_placeholder is None
    finally:
        destroy_qt_object(view)
