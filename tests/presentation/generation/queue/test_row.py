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

"""Verify one mounted generation queue row through real Qt widgets."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest

from sugarsubstitute_shared.presentation.fluent_tooltips import FluentToolTipFilter

from substitute.presentation.generation.queue_item_row import (
    GenerationQueueItemRow,
    QueueSurfaceMode,
)
from substitute.presentation.generation.queue_list_view import (
    QueueJobInteractionRole,
    QueueJobRowAction,
    QueueJobRowView,
    QueueJobVisualRole,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _row_view(
    *,
    status: str = "Pending",
    action: QueueJobRowAction | None = "cancel",
    visual_role: QueueJobVisualRole = "pending",
    interaction_role: QueueJobInteractionRole = "draggable",
    tooltip: str | None = None,
    prompt_tooltip: str | None = None,
    subtitle: str = "Next",
    can_open_snapshot: bool = False,
) -> QueueJobRowView:
    """Build one deterministic queue-row presentation model."""

    return QueueJobRowView(
        job_id="job-1",
        title="Workflow #001",
        subtitle=subtitle,
        status=status,
        action=action,
        visual_role=visual_role,
        interaction_role=interaction_role,
        pending_visual_index=0 if interaction_role == "draggable" else None,
        pending_dispatch_index=0 if interaction_role == "draggable" else None,
        tooltip=tooltip,
        prompt_tooltip=prompt_tooltip,
        can_open_snapshot=can_open_snapshot,
    )


def test_queue_row_uses_compact_stacked_text_contract() -> None:
    """Title and subtitle must remain a tight zero-gap two-line stack."""

    row = GenerationQueueItemRow(_row_view())
    try:
        text_layout = row._text_column.layout()
        assert text_layout is not None and text_layout.spacing() == 0
        assert 1 <= row._title_label.height() <= 20
        assert 1 <= row._subtitle_label.height() <= 20
        assert row._title_label.height() >= row._subtitle_label.height()
    finally:
        destroy_qt_object(row)


@pytest.mark.parametrize(
    ("status", "diagnostic", "prompt", "expected", "action_tooltip"),
    (
        pytest.param(
            "Pending",
            "diagnostic detail",
            "fox in moonlight",
            "fox in moonlight",
            "Cancel job",
            id="prompt-preview",
        ),
        pytest.param(
            "Failed",
            "diagnostic detail",
            None,
            "diagnostic detail",
            "Remove job",
            id="failure-diagnostic",
        ),
        pytest.param(
            "Failed",
            "diagnostic detail",
            "fox in moonlight",
            "diagnostic detail\n\nPrompt preview:\nfox in moonlight",
            "Remove job",
            id="failure-with-prompt",
        ),
    ),
)
def test_queue_row_routes_body_and_action_tooltips(
    status: str,
    diagnostic: str,
    prompt: str | None,
    expected: str,
    action_tooltip: str,
) -> None:
    """Body tooltip policy must preserve prompts and failure diagnostics exactly."""

    action: QueueJobRowAction = "remove" if status == "Failed" else "cancel"
    row = GenerationQueueItemRow(
        _row_view(
            status=status,
            action=action,
            visual_role="resolved" if status == "Failed" else "pending",
            interaction_role="context" if status == "Failed" else "draggable",
            tooltip=diagnostic,
            prompt_tooltip=prompt,
        )
    )
    try:
        assert row.toolTip() == expected
        assert row._text_column.toolTip() == ""
        assert row._title_label.toolTip() == ""
        assert row._subtitle_label.toolTip() == ""
        assert row._action_button.toolTip() == action_tooltip
        assert isinstance(row._tooltip_filter, FluentToolTipFilter)
        assert row._tooltip_filter.parent() is row
        assert row._text_column.findChild(FluentToolTipFilter) is None
        assert row._title_label.findChild(FluentToolTipFilter) is None
        assert row._subtitle_label.findChild(FluentToolTipFilter) is None
    finally:
        destroy_qt_object(row)


def test_queue_row_elides_long_subtitle_to_available_width() -> None:
    """Visible row copy must elide without discarding its diagnostic tooltip."""

    subtitle = (
        "Failed - Backend produced an extremely verbose generation failure reason"
    )
    row = GenerationQueueItemRow(
        _row_view(
            status="Failed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
            subtitle=subtitle,
            tooltip="diagnostic detail",
        )
    )
    try:
        row._text_column.resize(70, row._text_column.height())
        row._apply_text_elision()
        assert row._subtitle_label.text() != subtitle
        assert row._subtitle_label.text().endswith("…")
        assert row.toolTip() == "diagnostic detail"
    finally:
        destroy_qt_object(row)


@pytest.mark.parametrize(
    ("action", "signal_name", "tooltip"),
    (
        pytest.param("cancel", "cancelRequested", "Cancel job", id="cancel"),
        pytest.param("remove", "removeRequested", "Remove job", id="remove"),
    ),
)
def test_queue_row_action_emits_job_identity(
    action: QueueJobRowAction,
    signal_name: str,
    tooltip: str,
) -> None:
    """The visible action must emit the configured command for this exact job."""

    row = GenerationQueueItemRow(_row_view(action=action))
    spy = QSignalSpy(getattr(row, signal_name))
    try:
        QTest.mouseClick(row._action_button, Qt.MouseButton.LeftButton)
        assert spy.count() == 1
        assert spy.at(0) == ["job-1"]
        assert not row._action_button.isHidden()
        assert row._action_button.toolTip() == tooltip
    finally:
        destroy_qt_object(row)


def test_queue_row_snapshot_action_emits_job_identity() -> None:
    """Terminal context action must identify the snapshot-owning job."""

    row = GenerationQueueItemRow(
        _row_view(
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
            can_open_snapshot=True,
        )
    )
    spy = QSignalSpy(row.openSnapshotRequested)
    try:
        row._emit_open_snapshot_request()
        assert spy.count() == 1
        assert spy.at(0) == ["job-1"]
    finally:
        destroy_qt_object(row)


@pytest.mark.parametrize(
    ("surface_mode", "visual_role", "interaction_role", "cursor", "overlay_alpha"),
    (
        pytest.param(
            "panel",
            "pending",
            "draggable",
            Qt.CursorShape.OpenHandCursor,
            0,
            id="draggable",
        ),
        pytest.param(
            "panel",
            "resolved",
            "context",
            Qt.CursorShape.ArrowCursor,
            0,
            id="resolved",
        ),
        pytest.param(
            "flyout",
            "active",
            "none",
            Qt.CursorShape.ArrowCursor,
            25,
            id="flyout-active",
        ),
        pytest.param(
            "panel",
            "active",
            "none",
            Qt.CursorShape.ArrowCursor,
            25,
            id="panel-active",
        ),
    ),
)
def test_queue_row_projects_interaction_role(
    surface_mode: QueueSurfaceMode,
    visual_role: QueueJobVisualRole,
    interaction_role: QueueJobInteractionRole,
    cursor: Qt.CursorShape,
    overlay_alpha: int,
) -> None:
    """Cursor, tracking, and overlay must derive from the row interaction role."""

    row = GenerationQueueItemRow(
        _row_view(
            visual_role=visual_role,
            interaction_role=interaction_role,
        ),
        surface_mode=surface_mode,
    )
    try:
        assert row.cursor().shape() == cursor
        assert row.hasMouseTracking() is (interaction_role == "draggable")
        wait_for_qt_condition(
            lambda: row._interaction.current_overlay_color().alpha() == overlay_alpha
        )
        assert row._action_button.cursor().shape() == Qt.CursorShape.PointingHandCursor
        if interaction_role == "draggable":
            row._interaction.set_hovered(True)
            wait_for_qt_condition(
                lambda: row._interaction.current_overlay_color().alpha() == 25
            )
        assert "rgba(255, 255, 255, 25)" not in row.styleSheet()
    finally:
        destroy_qt_object(row)


def test_queue_row_updates_content_and_action_without_rebuilding_children() -> None:
    """Progress-to-terminal updates must preserve the mounted widget identities."""

    row = GenerationQueueItemRow(
        _row_view(status="Running", visual_role="active", interaction_role="none")
    )
    children = (row._title_label, row._subtitle_label, row._action_button)
    try:
        row.set_row(
            _row_view(
                status="Completed",
                action="remove",
                visual_role="resolved",
                interaction_role="context",
                subtitle="Completed - 1 output",
            )
        )
        assert (row._title_label, row._subtitle_label, row._action_button) == children
        assert row._full_title == "Workflow #001"
        assert row._full_subtitle == "Completed - 1 output"
        assert row._action_button.toolTip() == "Remove job"
        assert not row.hasMouseTracking()
    finally:
        destroy_qt_object(row)


@pytest.mark.parametrize(
    ("interaction_role", "expected_signals"),
    (
        pytest.param("draggable", 1, id="pending"),
        pytest.param("none", 0, id="active"),
    ),
)
def test_queue_row_body_children_respect_drag_eligibility(
    interaction_role: QueueJobInteractionRole,
    expected_signals: int,
) -> None:
    """Only draggable row-body children may initiate a reorder gesture."""

    row = GenerationQueueItemRow(
        _row_view(
            status="Running" if interaction_role == "none" else "Pending",
            visual_role="active" if interaction_role == "none" else "pending",
            interaction_role=interaction_role,
        )
    )
    spy = QSignalSpy(row.bodyPressed)
    body_child = row._body_drag_targets[0]
    try:
        row.resize(340, 72)
        row.show()
        QTest.mousePress(
            body_child,
            Qt.MouseButton.LeftButton,
            pos=QPoint(4, 4),
        )
        assert (spy.count() > 0) is bool(expected_signals)
        if expected_signals:
            assert all(spy.at(index)[0] == "job-1" for index in range(spy.count()))
    finally:
        destroy_qt_object(row)
