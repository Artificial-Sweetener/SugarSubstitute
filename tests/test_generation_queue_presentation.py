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

# mypy: disable-error-code=attr-defined
"""Presentation tests for generation queue row mapping and row intents."""

from __future__ import annotations

import importlib
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, cast

import pytest

from substitute.application.generation import GenerationQueueStateChange
from substitute.domain.generation import GenerationJobSnapshot, GenerationQueueJob
from substitute.presentation.generation.queue_counts import (
    generation_skip_action_available,
    pending_generation_queue_job_count,
)
from substitute.presentation.generation.queue_list_view import (
    QueueBucketDividerView,
    QueueJobRowView,
    queue_job_display_items,
    queue_job_row_views,
    should_show_pending_resolved_separator,
)
from substitute.presentation.generation.queue_reorder_controller import (
    PendingRowGeometry,
    dispatch_insertion_index_from_visual,
    pending_drop_insertion_index_for_y,
    service_target_index_for_drop,
)

_REAL_QT_XDIST_SKIP = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real queue row Qt drag tests require non-xdist execution on Windows",
)


def test_pending_generation_queue_job_count_excludes_active_and_terminal_jobs() -> None:
    """Queue count helper should count only jobs waiting for dispatch."""

    jobs = (
        _job("pending", status="pending"),
        _job("dispatching", status="dispatching"),
        _job("comfy-pending", status="comfy_pending"),
        _job("running", status="running"),
        _job("completed", status="completed"),
        _job("failed", status="failed"),
        _job("cancelled", status="cancelled"),
    )

    assert pending_generation_queue_job_count(jobs) == 1


@pytest.mark.parametrize(
    ("continuous_active", "queue_has_active", "pending_count", "expected"),
    (
        pytest.param(False, True, 0, False, id="normal-active-without-pending"),
        pytest.param(False, True, 1, True, id="normal-active-with-pending"),
        pytest.param(True, False, 0, True, id="continuous-without-visible-queue"),
        pytest.param(False, False, 1, False, id="pending-without-active"),
    ),
)
def test_generation_skip_action_available_requires_distinct_next_work(
    *,
    continuous_active: bool,
    queue_has_active: bool,
    pending_count: int,
    expected: bool,
) -> None:
    """Skip availability should distinguish continuous loops from normal stop."""

    assert (
        generation_skip_action_available(
            continuous_active=continuous_active,
            queue_has_active=queue_has_active,
            pending_queue_job_count=pending_count,
        )
        is expected
    )


def test_queue_display_items_render_final_scene_batch_state() -> None:
    """A single final observer state should still render every scene job."""

    jobs = (
        _job(
            "scene-1",
            status="pending",
            workflow_name="Scene 1",
            projected_output_run_number=1,
            projected_output_bucket_key="shared-bucket",
            projected_output_bucket_label="Shared",
            scene_run_id="scene-run",
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=3,
        ),
        _job(
            "scene-2",
            status="pending",
            workflow_name="Scene 2",
            projected_output_run_number=2,
            projected_output_bucket_key="shared-bucket",
            projected_output_bucket_label="Shared",
            scene_run_id="scene-run",
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=3,
        ),
        _job(
            "scene-3",
            status="pending",
            workflow_name="Scene 3",
            projected_output_run_number=3,
            projected_output_bucket_key="shared-bucket",
            projected_output_bucket_label="Shared",
            scene_run_id="scene-run",
            scene_key="street",
            scene_title="Street",
            scene_order=2,
            scene_count=3,
        ),
    )

    items = queue_job_display_items(jobs)
    rows = tuple(item for item in items if isinstance(item, QueueJobRowView))

    assert pending_generation_queue_job_count(jobs) == 3
    assert [row.job_id for row in rows] == ["scene-3", "scene-2", "scene-1"]
    assert [row.pending_dispatch_index for row in rows] == [2, 1, 0]
    assert [row.title for row in rows] == [
        "Scene 3 #003",
        "Scene 2 #002",
        "Scene 1 #001",
    ]


def _job(
    job_id: str,
    *,
    status: Literal[
        "pending",
        "dispatching",
        "comfy_pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    ],
    prompt_id: str | None = None,
    failure_message: str | None = None,
    failure_summary: str | None = None,
    failure_detail: str | None = None,
    last_output_path: Path | None = None,
    output_run_number: int | None = None,
    projected_output_run_number: int | None = None,
    progress_percent: float | None = None,
    output_count: int = 0,
    execution_duration_ms: float | None = None,
    created_at: datetime | None = None,
    workflow_name: str | None = None,
    positive_prompt_preview: str | None = None,
    output_bucket_key: str | None = None,
    output_bucket_label: str | None = None,
    projected_output_bucket_key: str | None = None,
    projected_output_bucket_label: str | None = None,
    scene_run_id: str | None = None,
    scene_key: str | None = None,
    scene_title: str | None = None,
    scene_order: int | None = None,
    scene_count: int | None = None,
) -> GenerationQueueJob:
    """Build one queue job DTO for presentation mapping tests."""

    resolved_workflow_name = workflow_name or f"Workflow {job_id}"
    return GenerationQueueJob(
        job_id=job_id,
        snapshot=GenerationJobSnapshot(
            workflow_id=f"workflow-{job_id}",
            workflow_name=resolved_workflow_name,
            sugar_script_text="# sugar",
            positive_prompt_preview=positive_prompt_preview,
            scene_run_id=scene_run_id,
            scene_key=scene_key,
            scene_title=scene_title,
            scene_order=scene_order,
            scene_count=scene_count,
        ),
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
        status=status,
        prompt_id=prompt_id,
        failure_message=failure_message,
        failure_summary=failure_summary,
        failure_detail=failure_detail,
        output_run_number=output_run_number,
        projected_output_run_number=projected_output_run_number,
        output_bucket_key=output_bucket_key,
        output_bucket_label=output_bucket_label,
        projected_output_bucket_key=projected_output_bucket_key,
        projected_output_bucket_label=projected_output_bucket_label,
        progress_percent=progress_percent,
        output_count=output_count,
        execution_duration_ms=execution_duration_ms,
        last_output_path=last_output_path,
    )


def test_queue_job_row_views_show_projected_and_committed_numbers() -> None:
    """Rows should display projected pending and committed active/resolved numbers."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="pending",
                projected_output_run_number=7,
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            ),
            _job(
                "b",
                status="running",
                prompt_id="prompt-b-123456",
                output_run_number=8,
                progress_percent=62.4,
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            ),
            _job(
                "c",
                status="completed",
                output_run_number=9,
                output_count=4,
                created_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
            ),
        )
    )

    assert [row.job_id for row in rows] == ["a", "b", "c"]
    assert [row.title for row in rows] == [
        "Workflow a #007",
        "Workflow b #008",
        "Workflow c #009",
    ]
    assert rows[0].subtitle == "Next"
    assert rows[1].subtitle == "62% complete"
    assert rows[2].subtitle == "Completed"
    assert rows[0].visual_role == "pending"
    assert rows[0].interaction_role == "draggable"
    assert rows[0].pending_visual_index == 0
    assert rows[0].pending_dispatch_index == 0
    assert rows[1].visual_role == "active"
    assert rows[1].interaction_role == "none"
    assert rows[2].visual_role == "resolved"
    assert rows[2].interaction_role == "context"
    assert rows[2].pending_visual_index is None
    assert rows[2].pending_dispatch_index is None
    assert rows[0].action == "cancel"
    assert rows[1].action == "cancel"
    assert rows[2].action == "remove"
    assert "prompt-b-123456" not in rows[1].subtitle


def test_completed_queue_row_view_shows_execution_duration() -> None:
    """Completed rows should append compact execution duration when available."""

    rows = queue_job_row_views(
        (
            _job(
                "completed",
                status="completed",
                execution_duration_ms=308000.0,
            ),
            _job(
                "subsecond",
                status="completed",
                execution_duration_ms=850.0,
            ),
        )
    )

    subtitles_by_job_id = {row.job_id: row.subtitle for row in rows}
    assert subtitles_by_job_id == {
        "completed": "Completed, 5m8s",
        "subsecond": "Completed, 0.8s",
    }


def test_queue_job_row_views_project_pending_title_number() -> None:
    """Pending rows without service projections should derive display numbers."""

    rows = queue_job_row_views((_job("a", status="pending"),))

    assert rows[0].title == "Workflow a #001"
    assert rows[0].subtitle == "Next"


def test_queue_job_row_views_show_pending_bottom_to_top_order() -> None:
    """Pending rows should display latest first while subtitles follow dispatch order."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="pending",
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                workflow_name="Shared",
            ),
            _job(
                "b",
                status="pending",
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
                workflow_name="Shared",
            ),
            _job(
                "c",
                status="pending",
                created_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
                workflow_name="Shared",
            ),
        )
    )

    assert [row.job_id for row in rows] == ["c", "b", "a"]
    assert [row.subtitle for row in rows] == [
        "Waiting - 2 ahead",
        "Waiting - 1 ahead",
        "Next",
    ]
    assert [row.title for row in rows] == [
        "Shared #003",
        "Shared #002",
        "Shared #001",
    ]
    assert [row.pending_visual_index for row in rows] == [0, 1, 2]
    assert [row.pending_dispatch_index for row in rows] == [2, 1, 0]


def test_queue_job_row_views_recompute_projection_after_dispatch_reorder() -> None:
    """Pending projections should follow service dispatch order."""

    original_rows = queue_job_row_views(
        (
            _job("a", status="pending", workflow_name="Shared"),
            _job("b", status="pending", workflow_name="Shared"),
        )
    )
    reordered_rows = queue_job_row_views(
        (
            _job("b", status="pending", workflow_name="Shared"),
            _job("a", status="pending", workflow_name="Shared"),
        )
    )

    assert {row.job_id: row.title for row in original_rows} == {
        "a": "Shared #001",
        "b": "Shared #002",
    }
    assert {row.job_id: row.title for row in reordered_rows} == {
        "b": "Shared #001",
        "a": "Shared #002",
    }


def test_queue_job_row_views_keep_workflow_projection_buckets_independent() -> None:
    """Pending output number projections should be scoped by workflow name."""

    rows = queue_job_row_views(
        (
            _job("a", status="pending", workflow_name="Shared"),
            _job("b", status="pending", workflow_name="Other"),
            _job("c", status="pending", workflow_name="Shared"),
        )
    )

    assert {row.job_id: row.title for row in rows} == {
        "a": "Shared #001",
        "b": "Other #001",
        "c": "Shared #002",
    }


def test_queue_job_row_views_scope_projection_by_output_bucket() -> None:
    """Bucket metadata should define the visible run-number namespace."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="pending",
                workflow_name="Shared",
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
            _job(
                "b",
                status="pending",
                workflow_name="Shared",
                projected_output_bucket_key="bucket-yesterday",
                projected_output_bucket_label="2026-05-11",
            ),
        )
    )

    assert {row.job_id: row.title for row in rows} == {
        "a": "Shared #001",
        "b": "Shared #001",
    }


def test_queue_job_display_items_insert_bucket_dividers_between_changed_buckets() -> (
    None
):
    """Display projection should mark only adjacent date bucket transitions."""

    items = queue_job_display_items(
        (
            _job(
                "today",
                status="pending",
                workflow_name="Workflow",
                projected_output_run_number=1,
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
            _job(
                "yesterday",
                status="completed",
                workflow_name="Workflow",
                output_run_number=1,
                output_bucket_key="bucket-yesterday",
                output_bucket_label="2026-05-11",
            ),
        )
    )

    assert [type(item) for item in items] == [
        QueueJobRowView,
        QueueBucketDividerView,
        QueueJobRowView,
    ]
    dividers = [item for item in items if isinstance(item, QueueBucketDividerView)]
    rows = [item for item in items if isinstance(item, QueueJobRowView)]
    assert [divider.label for divider in dividers] == ["2026-05-11"]
    assert [row.title for row in rows] == ["Workflow #001", "Workflow #001"]


def test_queue_job_display_items_skip_dividers_for_repeated_bucket() -> None:
    """Display projection should not add leading or repeated bucket dividers."""

    items = queue_job_display_items(
        (
            _job(
                "first",
                status="pending",
                workflow_name="Workflow",
                projected_output_run_number=1,
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
            _job(
                "second",
                status="pending",
                workflow_name="Workflow",
                projected_output_run_number=2,
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
        )
    )

    assert all(isinstance(item, QueueJobRowView) for item in items)


def test_queue_job_row_views_project_after_committed_active_number() -> None:
    """Pending projections should start after committed active row numbers."""

    rows = queue_job_row_views(
        (
            _job(
                "active",
                status="running",
                output_run_number=22,
                workflow_name="Shared",
            ),
            _job("pending", status="pending", workflow_name="Shared"),
        )
    )

    assert {row.job_id: row.title for row in rows} == {
        "active": "Shared #022",
        "pending": "Shared #023",
    }


def test_queue_job_row_views_put_next_pending_above_active_row() -> None:
    """The bottom pending row immediately above active should be the next job."""

    rows = queue_job_row_views(
        (
            _job(
                "active",
                status="running",
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            ),
            _job(
                "next",
                status="pending",
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            ),
            _job(
                "later",
                status="pending",
                created_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
            ),
        )
    )

    assert [row.job_id for row in rows] == ["later", "next", "active"]
    assert [row.visual_role for row in rows] == ["pending", "pending", "active"]
    assert rows[0].subtitle == "Waiting - 1 ahead"
    assert rows[1].subtitle == "Next"
    assert rows[1].pending_visual_index == 1
    assert rows[1].pending_dispatch_index == 0


def test_queue_job_row_views_show_cancelled_output_counts_only() -> None:
    """Cancelled subtitles should keep saved counts while completed rows stay compact."""

    rows = queue_job_row_views(
        (
            _job("completed-one", status="completed", output_count=1),
            _job("cancelled-none", status="cancelled", output_count=0),
            _job("cancelled-one", status="cancelled", output_count=1),
        )
    )

    subtitles_by_job_id = {row.job_id: row.subtitle for row in rows}
    assert subtitles_by_job_id["completed-one"] == "Completed"
    assert subtitles_by_job_id["cancelled-none"] == "Cancelled - No outputs saved"
    assert subtitles_by_job_id["cancelled-one"] == "Cancelled - 1 output saved"


def test_queue_job_row_views_show_failure_summary_and_tooltip_detail() -> None:
    """Failed rows should show compact summary and keep raw detail in tooltip."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="failed",
                prompt_id="prompt-a-123456",
                failure_message="Execution failed",
                failure_summary="Missing xformers",
                failure_detail="Traceback details",
                output_run_number=7,
            ),
        )
    )

    assert rows[0].title == "Workflow a #007"
    assert rows[0].subtitle == "Failed - Missing xformers"
    assert rows[0].tooltip is not None
    assert "prompt-a-123456" in rows[0].tooltip
    assert "Execution failed" in rows[0].tooltip
    assert "Traceback details" in rows[0].tooltip
    assert "prompt-a-123456" not in rows[0].subtitle


def test_queue_job_row_views_elide_long_failure_summary_but_keep_tooltip_detail() -> (
    None
):
    """Failed rows should bound visible reasons and keep full diagnostics in tooltip."""

    long_summary = (
        "Backend produced an extremely verbose generation failure reason " * 4
    )
    failure_message = "Execution failed while running the prompt."
    failure_detail = "Traceback details with many internal frames."

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="failed",
                failure_message=failure_message,
                failure_summary=long_summary,
                failure_detail=failure_detail,
            ),
        )
    )

    assert rows[0].subtitle.startswith("Failed - ")
    assert len(rows[0].subtitle) < len(f"Failed - {long_summary}")
    assert rows[0].subtitle.endswith("...")
    assert long_summary not in rows[0].subtitle
    assert rows[0].tooltip is not None
    assert long_summary.strip() in rows[0].tooltip
    assert failure_message in rows[0].tooltip
    assert failure_detail in rows[0].tooltip


def test_queue_job_row_views_bound_long_raw_failure_message_without_summary() -> None:
    """Failed rows should bound raw fallback reasons while tooltip keeps the source."""

    failure_message = (
        "A very long unclassified generation failure continued with enough detail "
        "to overflow a compact queue row if rendered directly."
    )

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="failed",
                failure_message=failure_message,
                failure_summary=None,
            ),
        )
    )

    assert rows[0].subtitle.startswith("Failed - ")
    assert len(rows[0].subtitle) < len(f"Failed - {failure_message}")
    assert rows[0].subtitle.endswith("...")
    assert rows[0].tooltip == failure_message


def test_queue_job_row_views_map_positive_prompt_preview_to_prompt_tooltip() -> None:
    """Rows should expose prompt previews separately from diagnostic tooltips."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="pending",
                positive_prompt_preview="fox in moonlight",
            ),
            _job("b", status="pending"),
        )
    )

    by_job_id = {row.job_id: row for row in rows}
    assert by_job_id["a"].prompt_tooltip == "fox in moonlight"
    assert by_job_id["a"].tooltip is None
    assert by_job_id["b"].prompt_tooltip is None


def test_queue_job_row_views_summarize_failed_raw_message() -> None:
    """Failed rows should summarize raw message when durable summary is absent."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="failed",
                failure_message="No module named 'xformers'",
            ),
        )
    )

    assert rows[0].subtitle == "Failed - Missing xformers"


def test_queue_job_row_views_expose_thumbnail_and_snapshot_open_state() -> None:
    """Terminal rows should expose snapshot-open state and lazy thumbnail paths."""

    rows = queue_job_row_views(
        (
            _job(
                "a",
                status="running",
                created_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
            ),
            _job(
                "b",
                status="completed",
                last_output_path=Path("out.png"),
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            ),
            _job(
                "c",
                status="cancelled",
                last_output_path=Path("partial.png"),
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )

    assert rows[0].thumbnail_path is None
    assert rows[0].can_open_snapshot is False
    assert rows[1].thumbnail_path == Path("out.png")
    assert rows[1].can_open_snapshot is True
    assert rows[2].thumbnail_path == Path("partial.png")
    assert rows[2].can_open_snapshot is True


def test_queue_job_row_views_map_all_status_roles() -> None:
    """Queue rows should expose active, draggable, and resolved interaction roles."""

    rows = queue_job_row_views(
        (
            _job("dispatching", status="dispatching"),
            _job("comfy", status="comfy_pending"),
            _job("running", status="running"),
            _job("pending", status="pending"),
            _job("completed", status="completed"),
            _job("failed", status="failed"),
            _job("cancelled", status="cancelled"),
        )
    )

    roles_by_job_id = {
        row.job_id: (
            row.visual_role,
            row.interaction_role,
            row.pending_visual_index,
            row.pending_dispatch_index,
        )
        for row in rows
    }
    assert roles_by_job_id["dispatching"] == ("active", "none", None, None)
    assert roles_by_job_id["comfy"] == ("active", "none", None, None)
    assert roles_by_job_id["running"] == ("active", "none", None, None)
    assert roles_by_job_id["pending"] == ("pending", "draggable", 0, 0)
    assert roles_by_job_id["completed"] == ("resolved", "context", None, None)
    assert roles_by_job_id["failed"] == ("resolved", "context", None, None)
    assert roles_by_job_id["cancelled"] == ("resolved", "context", None, None)


def test_queue_rows_show_resolved_separator_only_without_active_row() -> None:
    """Resolved separator should appear only when no active row already divides rows."""

    assert should_show_pending_resolved_separator(
        queue_job_row_views(
            (
                _job("pending", status="pending"),
                _job("completed", status="completed"),
            )
        )
    )
    assert not should_show_pending_resolved_separator(
        queue_job_row_views(
            (
                _job("active", status="running"),
                _job("pending", status="pending"),
                _job("completed", status="completed"),
            )
        )
    )


class _Signal:
    """Minimal Qt-like signal used by widget stubs."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Create an empty connection list."""

        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback: Callable[..., None]) -> None:
        """Record one connected callback."""

        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        """Invoke all connected callbacks."""

        for callback in self._callbacks:
            if callable(callback):
                callback(*args)
                continue
            emit = getattr(callback, "emit", None)
            if callable(emit):
                emit(*args)


class _SignalDescriptor:
    """Create one signal instance per widget instance."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Store the instance attribute name lazily."""

        self._name = ""

    def __set_name__(self, _owner: object, name: str) -> None:
        """Remember the target instance dictionary key."""

        self._name = f"_{name}_signal"

    def __get__(self, instance: object, _owner: object) -> _SignalDescriptor | _Signal:
        """Return a per-instance signal object."""

        if instance is None:
            return self
        signal = getattr(instance, self._name, None)
        if signal is None:
            signal = _Signal()
            setattr(instance, self._name, signal)
        return signal


class _Widget:
    """Generic QWidget stand-in for queue row construction."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Capture basic widget state used in assertions."""

        self.visible = True
        self.tooltip: str | None = None
        self.deleted = False
        self.style = ""
        self.cursor: object | None = None
        self.mouse_tracking: bool | None = None
        self.event_filters: list[object] = []
        self.geometry: tuple[object, ...] | None = None
        self.parent: object | None = None
        self.text = ""
        self.minimum_height: int | None = None
        self.pixmap: object | None = None
        self.updated = False
        self.widget_y = 0
        self.widget_x = 0
        self.widget_width = 320
        self.widget_height = 40
        self.object_name = ""
        self._font = _Font()
        self._layout: _Layout | None = None

    def setObjectName(self, name: str) -> None:
        """Record object-name assignment."""

        self.object_name = name

    def setStyleSheet(self, _style: str) -> None:
        """Accept stylesheet assignment."""

        self.style = _style

    def setFixedWidth(self, _width: int) -> None:
        """Accept fixed-width assignment."""

    def setFixedHeight(self, _height: int) -> None:
        """Accept fixed-height assignment."""

        self.widget_height = _height

    def font(self) -> "_Font":
        """Return the recorded widget font."""

        return self._font

    def setFont(self, font: "_Font") -> None:
        """Record font assignment."""

        self._font = font

    def layout(self) -> "_Layout | None":
        """Return the layout assigned to this widget."""

        return self._layout

    def setMaximumHeight(self, _height: int) -> None:
        """Accept maximum-height assignment."""

    def setMinimumHeight(self, _height: int) -> None:
        """Accept minimum-height assignment."""

        self.minimum_height = _height

    def setAlignment(self, _alignment: object) -> None:
        """Accept alignment assignment."""

    def setTextInteractionFlags(self, _flags: object) -> None:
        """Accept text interaction flags."""

    def setText(self, text: str) -> None:
        """Record text assignment."""

        self.text = text

    def clear(self) -> None:
        """Clear pixmap content."""

        self.pixmap = None

    def setPixmap(self, pixmap: object) -> None:
        """Record pixmap assignment."""

        self.pixmap = pixmap

    def setToolTip(self, tooltip: str) -> None:
        """Record tooltip assignment."""

        self.tooltip = tooltip

    def setFixedSize(self, _width: int, _height: int) -> None:
        """Accept fixed-size assignment."""

        self.widget_width = _width
        self.widget_height = _height

    def setCursor(self, _cursor: object) -> None:
        """Accept cursor assignment."""

        self.cursor = _cursor

    def setMouseTracking(self, enabled: bool) -> None:
        """Record mouse tracking assignment."""

        self.mouse_tracking = enabled

    def installEventFilter(self, event_filter: object) -> None:
        """Record installed event filters."""

        self.event_filters.append(event_filter)

    def eventFilter(self, _watched: object, _event: object) -> bool:
        """Return no event consumption by default."""

        return False

    def setGeometry(self, *geometry: object) -> None:
        """Record geometry assignment."""

        self.geometry = geometry

    def setParent(self, parent: object | None) -> None:
        """Record parent assignment."""

        self.parent = parent

    def setWindowOpacity(self, _opacity: float) -> None:
        """Accept opacity assignment."""

    def setGraphicsEffect(self, _effect: object) -> None:
        """Accept graphics-effect assignment."""

    def move(self, x: int, y: int) -> None:
        """Record widget movement."""

        self.widget_x = x
        self.widget_y = y

    def pos(self) -> object:
        """Return a QPoint-like position."""

        return (self.widget_x, self.widget_y)

    def raise_(self) -> None:
        """Accept widget raise requests."""

    def y(self) -> int:
        """Return a deterministic widget y coordinate."""

        return self.widget_y

    def height(self) -> int:
        """Return a deterministic widget height."""

        return self.widget_height

    def width(self) -> int:
        """Return a deterministic widget width."""

        return self.widget_width

    def isVisible(self) -> bool:
        """Return recorded visibility."""

        return self.visible

    def show(self) -> None:
        """Record visible state."""

        self.visible = True

    def hide(self) -> None:
        """Record hidden state."""

        self.visible = False

    def grab(self) -> object:
        """Return a deterministic pixmap stand-in."""

        return _Pixmap()

    def mousePressEvent(self, _event: object) -> None:
        """Accept mouse press events."""

    def mouseMoveEvent(self, _event: object) -> None:
        """Accept mouse move events."""

    def mouseReleaseEvent(self, _event: object) -> None:
        """Accept mouse release events."""

    def setVisible(self, visible: bool) -> None:
        """Record visibility state."""

        self.visible = visible

    def update(self) -> None:
        """Record repaint requests."""

        self.updated = True

    def deleteLater(self) -> None:
        """Record deferred deletion."""

        self.deleted = True


class _Layout:
    """Minimal layout stand-in."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Create a no-op layout and attach it to the parent widget."""

        self.items: list[object] = []
        self.stretches: list[int] = []
        self.margins: tuple[object, ...] | None = None
        self.spacing = 0
        if _args and isinstance(_args[0], _Widget):
            _args[0]._layout = self

    def setContentsMargins(self, *_args: object) -> None:
        """Accept margin assignment."""

        self.margins = _args

    def setSpacing(self, spacing: int) -> None:
        """Record spacing assignment."""

        self.spacing = spacing

    def addWidget(self, *_args: object) -> None:
        """Accept child widget insertion."""

        self.items.append(_args[0])
        stretch = _args[1] if len(_args) > 1 and isinstance(_args[1], int) else 0
        self.stretches.append(stretch)

    def addLayout(self, *_args: object) -> None:
        """Accept child layout insertion."""

    def addStretch(self, *_args: object) -> None:
        """Accept stretch insertion."""

        self.items.append(None)
        stretch = _args[0] if _args and isinstance(_args[0], int) else 0
        self.stretches.append(stretch)

    def count(self) -> int:
        """Return item count."""

        return len(self.items)

    def takeAt(self, index: int) -> object:
        """Remove and return one layout item wrapper."""

        item = self.items.pop(index)
        self.stretches.pop(index)
        return types.SimpleNamespace(widget=lambda: item)


class _Button(_Widget):
    """Button stand-in with a clicked signal."""

    def __init__(self, *args: object, **_kwargs: object) -> None:
        """Create a clicked signal."""

        super().__init__(*args, **_kwargs)
        self.clicked = _Signal()
        self.icon: object | None = args[0] if args else None
        self.icon_size: object | None = None

    def setIcon(self, icon: object) -> None:
        """Record icon assignment."""

        self.icon = icon

    def setIconSize(self, icon_size: object) -> None:
        """Record icon-size assignment."""

        self.icon_size = icon_size


class _FluentIconBase:
    """Fluent icon base stand-in that can be mixed with Enum."""


class _Font:
    """Minimal mutable font stand-in."""

    def __init__(self, point_size: int = 10) -> None:
        """Store a point size."""

        self._point_size = point_size

    def pointSize(self) -> int:
        """Return the stored point size."""

        return self._point_size

    def setPointSize(self, point_size: int) -> None:
        """Record a point-size assignment."""

        self._point_size = point_size


class _QSize:
    """QSize stand-in for queue thumbnail tests."""

    def __init__(self, width: int, height: int) -> None:
        """Store dimensions."""

        self._width = width
        self._height = height

    def width(self) -> int:
        """Return width."""

        return self._width

    def height(self) -> int:
        """Return height."""

        return self._height


class _Pixmap:
    """Null QPixmap stand-in for queue thumbnail tests."""

    def __init__(self, *_args: object) -> None:
        """Create null pixmap."""

    def isNull(self) -> bool:
        """Return true for test pixmaps."""

        return True


class _QColor:
    """QColor stand-in for shared queue interaction color tests."""

    def __init__(
        self,
        red: object,
        green: int | None = None,
        blue: int | None = None,
        alpha: int = 255,
    ) -> None:
        """Store integer channels, accepting string colors as opaque black."""

        if isinstance(red, str):
            self._red = 0
            self._green = 0
            self._blue = 0
            self._alpha = 255
            return
        self._red = int(cast(Any, red))
        self._green = int(green or 0)
        self._blue = int(blue or 0)
        self._alpha = int(alpha)

    def red(self) -> int:
        """Return red channel."""

        return self._red

    def green(self) -> int:
        """Return green channel."""

        return self._green

    def blue(self) -> int:
        """Return blue channel."""

        return self._blue

    def alpha(self) -> int:
        """Return alpha channel."""

        return self._alpha

    def setAlpha(self, alpha: int) -> None:
        """Record alpha channel updates."""

        self._alpha = alpha


class _QObject:
    """QObject stand-in for interaction helper tests using queue stubs."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Accept QObject construction."""

    def eventFilter(self, _watched: object, _event: object) -> bool:
        """Return the default unhandled event-filter result."""

        return False


class _QPropertyAnimation:
    """QPropertyAnimation stand-in for queue row stub tests."""

    def __init__(self, *args: object, **_kwargs: object) -> None:
        """Store no animation state."""

        self._target = args[0] if args else None
        self._property_name = args[1] if len(args) > 1 else b""
        self._end_value: object = 0

    def setDuration(self, _duration: int) -> None:
        """Accept duration assignment."""

    def stop(self) -> None:
        """Accept stop calls."""

    def setStartValue(self, _value: object) -> None:
        """Accept start value assignment."""

    def setEndValue(self, _value: object) -> None:
        """Accept end value assignment."""

        self._end_value = _value

    def start(self) -> None:
        """Immediately apply the end value for deterministic tests."""

        if self._property_name == b"overlayAlpha":
            setter = getattr(self._target, "_set_overlay_alpha", None)
            if callable(setter):
                setter(self._end_value)


class _QRect:
    """QRect stand-in for queue row stub imports."""

    def adjusted(self, *_args: object) -> "_QRect":
        """Return self for adjusted rectangle calls."""

        return self


class _QRectF:
    """QRectF stand-in for queue row stub imports."""

    def __init__(self, _rect: object) -> None:
        """Accept source rectangle."""


class _QPainterPath:
    """QPainterPath stand-in for queue row stub imports."""

    def addRoundedRect(
        self,
        _rect: object,
        _x_radius: float,
        _y_radius: float,
    ) -> None:
        """Accept rounded-rect path commands."""


class _QPainter:
    """QPainter stand-in for shared row feedback imports."""

    RenderHint = types.SimpleNamespace(Antialiasing="antialiasing")

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Accept painter construction."""

    def setRenderHint(self, *_args: object) -> None:
        """Accept render hint assignment."""

    def setPen(self, *_args: object) -> None:
        """Accept pen assignment."""

    def setBrush(self, *_args: object) -> None:
        """Accept brush assignment."""

    def drawPath(self, *_args: object) -> None:
        """Accept path drawing."""


class _QEvent:
    """QEvent stand-in exposing mouse event types."""

    class Type:
        """Mouse event type names used by queue row tests."""

        MouseButtonPress = "mouse-press"
        MouseMove = "mouse-move"
        MouseButtonRelease = "mouse-release"


def _Property(_type: object, getter: object, setter: object) -> object:
    """Return a Python property for Qt Property declarations in stubs."""

    return property(cast(Any, getter), cast(Any, setter))


def _install_row_interaction_stub_dependencies(
    qtcore: types.ModuleType,
    qtgui: types.ModuleType,
    qfw: types.ModuleType,
) -> None:
    """Install Qt symbols required by the shared row interaction helper."""

    qtcore.QEvent = _QEvent
    qtcore.QObject = _QObject
    qtcore.QPropertyAnimation = _QPropertyAnimation
    qtcore.QRect = _QRect
    qtcore.QRectF = _QRectF
    qtcore.Property = _Property
    qtgui.QPainter = _QPainter
    qtgui.QPainterPath = _QPainterPath
    qfw.isDarkTheme = lambda: True
    qfw_common = types.ModuleType("qfluentwidgets.common")
    qfw_style_sheet = types.ModuleType("qfluentwidgets.common.style_sheet")
    qfw_style_sheet.isDarkTheme = lambda: True
    sys.modules["qfluentwidgets.common"] = qfw_common
    sys.modules["qfluentwidgets.common.style_sheet"] = qfw_style_sheet


class _MouseEvent:
    """Mouse event stand-in for queue row drag tests."""

    def __init__(self, event_type: object, y: int, *, button: object = "left") -> None:
        """Store event type, button, and y coordinate."""

        self._event_type = event_type
        self._button = button
        self._y = y

    def type(self) -> object:
        """Return event type."""

        return self._event_type

    def button(self) -> object:
        """Return mouse button."""

        return self._button

    def pos(self) -> object:
        """Return a QPoint-like position."""

        class _Point:
            """Tiny point with subtraction and y access."""

            def __init__(self, y: int) -> None:
                self._y = y

            def __sub__(self, other: object) -> "_Point":
                other_y = cast(Any, other).y()
                return _Point(self._y - int(other_y))

            def y(self) -> int:
                return self._y

            def manhattanLength(self) -> int:
                return abs(self._y)

        return _Point(self._y)


def _point(y: int) -> object:
    """Return a QPoint-like object for rows-view drag tests."""

    return types.SimpleNamespace(y=lambda: y)


def _remove_generation_queue_modules() -> None:
    """Force queue presentation modules to re-import against the active Qt modules."""

    for module_name in (
        "substitute.presentation.generation.queue_item_row",
        "substitute.presentation.generation.queue_rows_view",
        "substitute.presentation.widgets.row_interaction_feedback",
        "substitute.presentation.shell.chrome_style",
        "qfluentwidgets.common.config",
    ):
        sys.modules.pop(module_name, None)


def _clear_gui_stubs_for_real_qt() -> None:
    """Reload queue modules before real Qt queue tests import them."""

    qtcore_module = sys.modules.get("PySide6.QtCore")
    qfluent_module = sys.modules.get("qfluentwidgets")
    qtcore_qobject = getattr(qtcore_module, "QObject", None)
    qobject_module = getattr(qtcore_qobject, "__module__", "")
    clear_pyside = qtcore_module is not None and (
        not hasattr(qtcore_module, "__file__")
        or (isinstance(qobject_module, str) and qobject_module.startswith("tests."))
    )
    clear_qfluent = qfluent_module is not None and not hasattr(
        qfluent_module, "__file__"
    )
    for module_name in list(sys.modules):
        if clear_pyside and (
            module_name == "PySide6" or module_name.startswith("PySide6.")
        ):
            sys.modules.pop(module_name, None)
        if clear_qfluent and (
            module_name == "qfluentwidgets" or module_name.startswith("qfluentwidgets.")
        ):
            sys.modules.pop(module_name, None)
        if module_name.startswith("qfluentwidgets."):
            module = sys.modules.get(module_name)
            if module is not None and not hasattr(module, "__file__"):
                sys.modules.pop(module_name, None)
    _remove_generation_queue_modules()
    sys.modules.pop("sugarsubstitute_shared.presentation.fluent_tooltips", None)


def _install_cursor_tooltip_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a lightweight cursor-tooltip helper module for row stubs."""

    cursor_tooltip = types.ModuleType(
        "sugarsubstitute_shared.presentation.fluent_tooltips"
    )

    class _CursorToolTipFilter:
        """Record cursor-tooltip filter construction for row tests."""

        def __init__(
            self,
            owner: object,
            *,
            show_delay_ms: int,
            watched_widgets: tuple[object, ...],
        ) -> None:
            """Store construction details."""

            self._owner = owner
            self._show_delay_ms = show_delay_ms
            self.watched_widgets = watched_widgets

    def _install_cursor_tooltip_filter(
        owner: object,
        *watched_widgets: object,
        show_delay_ms: int = 300,
        **_kwargs: object,
    ) -> _CursorToolTipFilter:
        """Install one test cursor-tooltip filter on watched widgets."""

        tooltip_filter = _CursorToolTipFilter(
            owner,
            show_delay_ms=show_delay_ms,
            watched_widgets=watched_widgets,
        )
        for widget in watched_widgets or (owner,):
            widget.installEventFilter(tooltip_filter)
        return tooltip_filter

    cursor_tooltip.FluentToolTipFilter = _CursorToolTipFilter
    cursor_tooltip.ensure_fluent_tooltip_filter = _install_cursor_tooltip_filter
    cursor_tooltip.set_fluent_tooltip_text = lambda target, text: target.setToolTip(
        text
    )
    monkeypatch.setitem(
        sys.modules,
        "sugarsubstitute_shared.presentation.fluent_tooltips",
        cursor_tooltip,
    )


def _install_queue_row_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install PySide and qfluent stubs needed by queue row tests."""

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        NoTextInteraction="no-text",
        ArrowCursor="arrow",
        OpenHandCursor="open-hand",
        ClosedHandCursor="closed-hand",
        PointingHandCursor="pointing",
        LeftButton="left",
        AlignRight=1,
        AlignVCenter=2,
        AlignCenter=4,
    )
    qtcore.QEvent = _QEvent
    qtcore.QObject = _QObject
    qtcore.QPropertyAnimation = _QPropertyAnimation
    qtcore.QRect = _QRect
    qtcore.QRectF = _QRectF
    qtcore.QSize = _QSize
    qtcore.Property = _Property
    qtcore.Signal = _SignalDescriptor
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QPixmap = _Pixmap
    qtgui.QColor = _QColor
    qtgui.QPainter = _QPainter
    qtgui.QPainterPath = _QPainterPath
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QFrame = _Widget
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget
    qfw = types.ModuleType("qfluentwidgets")
    qfw.FluentIconBase = _FluentIconBase
    qfw.FluentIcon = types.SimpleNamespace(CLOSE=object(), DELETE=object())
    qfw.Theme = types.SimpleNamespace(AUTO="auto")
    qfw.getIconColor = lambda _theme: "black"
    qfw.isDarkTheme = lambda: True
    qfw.TransparentToolButton = _Button
    qfw_common = types.ModuleType("qfluentwidgets.common")
    qfw_style_sheet = types.ModuleType("qfluentwidgets.common.style_sheet")
    qfw_style_sheet.isDarkTheme = lambda: True
    qfw_components = types.ModuleType("qfluentwidgets.components")
    qfw_widgets = types.ModuleType("qfluentwidgets.components.widgets")
    qfw_tool_tip = types.ModuleType("qfluentwidgets.components.widgets.tool_tip")
    cursor_tooltip = types.ModuleType(
        "sugarsubstitute_shared.presentation.fluent_tooltips"
    )
    localization = types.ModuleType("substitute.presentation.localization")
    localization.LocalizedCaptionLabel = _Widget

    class _ToolTipFilter:
        """Record QFluent tooltip-filter construction for queue row tests."""

        def __init__(self, widget: object, **kwargs: object) -> None:
            """Store construction details."""

            self.widget = widget
            self.kwargs = kwargs

    qfw_tool_tip.ToolTipFilter = _ToolTipFilter

    class _CursorToolTipFilter:
        """Record cursor-tooltip filter construction for queue row tests."""

        def __init__(
            self,
            owner: object,
            *,
            show_delay_ms: int,
            watched_widgets: tuple[object, ...],
        ) -> None:
            """Store construction details."""

            self._owner = owner
            self._show_delay_ms = show_delay_ms
            self.watched_widgets = watched_widgets

    def _install_cursor_tooltip_filter(
        owner: object,
        *watched_widgets: object,
        show_delay_ms: int = 300,
        **_kwargs: object,
    ) -> _CursorToolTipFilter:
        """Install one test cursor-tooltip filter on watched widgets."""

        tooltip_filter = _CursorToolTipFilter(
            owner,
            show_delay_ms=show_delay_ms,
            watched_widgets=watched_widgets,
        )
        for widget in watched_widgets or (owner,):
            widget.installEventFilter(tooltip_filter)
        return tooltip_filter

    cursor_tooltip.FluentToolTipFilter = _CursorToolTipFilter
    cursor_tooltip.ensure_fluent_tooltip_filter = _install_cursor_tooltip_filter
    cursor_tooltip.set_fluent_tooltip_text = lambda target, text: target.setToolTip(
        text
    )
    shiboken = types.ModuleType("shiboken6")
    shiboken.isValid = lambda _obj: True

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "shiboken6", shiboken)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.localization",
        localization,
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.components", qfw_components)
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.components.widgets",
        qfw_widgets,
    )
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.components.widgets.tool_tip",
        qfw_tool_tip,
    )
    monkeypatch.setitem(
        sys.modules,
        "sugarsubstitute_shared.presentation.fluent_tooltips",
        cursor_tooltip,
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.common", qfw_common)
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.common.style_sheet",
        qfw_style_sheet,
    )
    _remove_generation_queue_modules()


def test_queue_row_uses_compact_stacked_text_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue row title and subtitle should use Hunters Dream compact text stacking."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #001",
        subtitle="Next",
        status="Pending",
        action="cancel",
    )

    row = module.GenerationQueueItemRow(row_view)

    assert row._text_column.layout().spacing == 0
    assert row._title_label.font().pointSize() == 11
    assert row._title_label.style == ""
    assert row._title_label.widget_height == 14
    assert row._subtitle_label.font().pointSize() == 9
    assert row._subtitle_label.style == ""
    assert row._subtitle_label.widget_height == 14


def test_queue_row_applies_cursor_prompt_tooltip_to_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue rows should expose one cursor-anchored prompt tooltip through body targets."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #001",
        subtitle="Next",
        status="Pending",
        action="cancel",
        tooltip="diagnostic detail",
        prompt_tooltip="fox in moonlight",
    )

    row = module.GenerationQueueItemRow(row_view)

    assert row.tooltip == "fox in moonlight"
    assert row._text_column.tooltip == ""
    assert row._title_label.tooltip == ""
    assert row._subtitle_label.tooltip == ""
    assert row._action_button.tooltip == "Cancel job"
    assert row._tooltip_filter is not None
    assert row._tooltip_filter._owner is row
    assert row._tooltip_filter._show_delay_ms == 600
    assert len(row.event_filters) == 1
    assert len(row._text_column.event_filters) == 2
    assert len(row._title_label.event_filters) == 2
    assert len(row._subtitle_label.event_filters) == 2


def test_queue_row_falls_back_to_diagnostic_tooltip_without_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows without prompt previews should keep existing diagnostic tooltip behavior."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #001",
        subtitle="Failed - Missing xformers",
        status="Failed",
        action="remove",
        tooltip="diagnostic detail",
        prompt_tooltip=None,
    )

    row = module.GenerationQueueItemRow(row_view)

    assert row.tooltip == "diagnostic detail"
    assert row._text_column.tooltip == ""
    assert row._action_button.tooltip == "Remove job"


def test_queue_row_failed_tooltip_keeps_diagnostics_when_prompt_preview_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed rows should expose diagnostics even when prompt preview text exists."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #001",
        subtitle="Failed - Missing xformers",
        status="Failed",
        action="remove",
        tooltip="diagnostic detail",
        prompt_tooltip="fox in moonlight",
    )

    row = module.GenerationQueueItemRow(row_view)

    assert row.tooltip.startswith("diagnostic detail")
    assert "\n\nPrompt preview:\nfox in moonlight" in row.tooltip
    assert row._text_column.tooltip == ""
    assert row._title_label.tooltip == ""
    assert row._subtitle_label.tooltip == ""
    assert row._action_button.tooltip == "Remove job"


def test_queue_row_elides_long_subtitle_to_available_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue row labels should elide long text instead of widening the row."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    full_subtitle = (
        "Failed - Backend produced an extremely verbose generation failure reason"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #001",
        subtitle=full_subtitle,
        status="Failed",
        action="remove",
        tooltip="diagnostic detail",
    )
    row = module.GenerationQueueItemRow(row_view)

    row._text_column.widget_width = 70
    row._apply_text_elision()

    assert row._subtitle_label.text != full_subtitle
    assert row._subtitle_label.text.endswith("...")
    assert row.tooltip == "diagnostic detail"


def test_queue_row_x_button_emits_cancel_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking a row X button should emit the row job id."""

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        NoTextInteraction="no-text",
        ArrowCursor="arrow",
        OpenHandCursor="open-hand",
        ClosedHandCursor="closed-hand",
        PointingHandCursor="pointing",
        AlignRight=1,
        AlignVCenter=2,
    )
    qtcore.QSize = _QSize
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QPixmap = _Pixmap
    qtgui.QColor = _QColor
    qtcore.Signal = _SignalDescriptor
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QFrame = _Widget
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget
    qfw = types.ModuleType("qfluentwidgets")
    qfw.FluentIcon = types.SimpleNamespace(CLOSE=object())
    qfw.TransparentToolButton = _Button
    _install_row_interaction_stub_dependencies(qtcore, qtgui, qfw)

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)
    _install_cursor_tooltip_stub(monkeypatch)
    sys.modules.pop("substitute.presentation.generation.queue_item_row", None)
    sys.modules.pop("substitute.presentation.widgets.row_interaction_feedback", None)

    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow",
        subtitle="#1 - Waiting",
        status="Waiting",
        action="cancel",
    )
    row = module.GenerationQueueItemRow(row_view)
    emitted: list[str] = []
    row.cancelRequested.connect(lambda job_id: emitted.append(job_id))

    row._action_button.clicked.emit()

    assert emitted == ["job-1"]
    assert row._action_button.visible is True
    assert row._action_button.tooltip == "Cancel job"


def test_queue_row_trash_button_emits_remove_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking a terminal row trash button should emit the row remove intent."""

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        NoTextInteraction="no-text",
        ArrowCursor="arrow",
        OpenHandCursor="open-hand",
        ClosedHandCursor="closed-hand",
        PointingHandCursor="pointing",
        AlignRight=1,
        AlignVCenter=2,
    )
    qtcore.QSize = _QSize
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QPixmap = _Pixmap
    qtgui.QColor = _QColor
    qtcore.Signal = _SignalDescriptor
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QFrame = _Widget
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget
    qfw = types.ModuleType("qfluentwidgets")
    qfw.FluentIcon = types.SimpleNamespace(CLOSE=object(), DELETE=object())
    qfw.TransparentToolButton = _Button
    _install_row_interaction_stub_dependencies(qtcore, qtgui, qfw)

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)
    _install_cursor_tooltip_stub(monkeypatch)
    sys.modules.pop("substitute.presentation.generation.queue_item_row", None)
    sys.modules.pop("substitute.presentation.widgets.row_interaction_feedback", None)

    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow",
        subtitle="#1 - Failed",
        status="Failed",
        action="remove",
    )
    row = module.GenerationQueueItemRow(row_view)
    emitted: list[str] = []
    row.removeRequested.connect(lambda job_id: emitted.append(job_id))

    row._action_button.clicked.emit()

    assert emitted == ["job-1"]
    assert row._action_button.visible is True
    assert row._action_button.tooltip == "Remove job"


def test_queue_row_open_snapshot_intent_emits_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminal row context action helper should emit snapshot-open intent."""

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        NoTextInteraction="no-text",
        ArrowCursor="arrow",
        OpenHandCursor="open-hand",
        ClosedHandCursor="closed-hand",
        PointingHandCursor="pointing",
        AlignRight=1,
        AlignVCenter=2,
    )
    qtcore.QSize = _QSize
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QPixmap = _Pixmap
    qtgui.QColor = _QColor
    qtcore.Signal = _SignalDescriptor
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QFrame = _Widget
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget
    qfw = types.ModuleType("qfluentwidgets")
    qfw.FluentIcon = types.SimpleNamespace(CLOSE=object(), DELETE=object())
    qfw.TransparentToolButton = _Button
    _install_row_interaction_stub_dependencies(qtcore, qtgui, qfw)

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)
    _install_cursor_tooltip_stub(monkeypatch)
    sys.modules.pop("substitute.presentation.generation.queue_item_row", None)
    sys.modules.pop("substitute.presentation.widgets.row_interaction_feedback", None)

    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow",
        subtitle="#1 - Completed",
        status="Completed",
        action="remove",
        can_open_snapshot=True,
    )
    row = module.GenerationQueueItemRow(row_view)
    emitted: list[str] = []
    row.openSnapshotRequested.connect(lambda job_id: emitted.append(job_id))

    row._emit_open_snapshot_request()

    assert emitted == ["job-1"]


def test_queue_row_applies_draggable_cursor_and_hover_style(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Draggable pending rows should expose grab affordances and overlay on hover."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Next",
        status="Pending",
        action="cancel",
        interaction_role="draggable",
        pending_visual_index=0,
        pending_dispatch_index=0,
    )

    row = module.GenerationQueueItemRow(row_view)

    assert row.cursor == "open-hand"
    assert row.mouse_tracking is True
    assert row._interaction.current_overlay_color().alpha() == 0
    row._interaction.set_hovered(True)
    assert row._interaction.current_overlay_color().alpha() == 25
    assert row._action_button.cursor == "pointing"


def test_queue_row_applies_non_draggable_cursor_for_resolved_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolved rows should not present a grab affordance."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Completed - 1 output",
        status="Completed",
        action="remove",
        visual_role="resolved",
        interaction_role="context",
    )

    row = module.GenerationQueueItemRow(row_view)

    assert row.cursor == "arrow"
    assert row.mouse_tracking is False
    assert row._action_button.cursor == "pointing"


def test_queue_row_applies_flyout_active_highlight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flyout active rows should use the shared painted list-item overlay."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="62% complete",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )

    row = module.GenerationQueueItemRow(row_view, surface_mode="flyout")

    assert row.cursor == "arrow"
    assert row._interaction.current_overlay_color().alpha() == 25
    assert "rgba(255, 255, 255, 25)" not in row.style


def test_queue_row_applies_panel_active_highlight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panel active rows should use the same painted overlay as flyout rows."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="62% complete",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )

    row = module.GenerationQueueItemRow(row_view, surface_mode="panel")

    assert row.cursor == "arrow"
    assert row._interaction.current_overlay_color().alpha() == 25
    assert "rgba(255, 255, 255, 25)" not in row.style


def test_queue_row_set_row_updates_content_and_action_in_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """set_row should refresh labels and action state without rebuilding children."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Running",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )
    row = module.GenerationQueueItemRow(row_view)
    title_label = row._title_label
    subtitle_label = row._subtitle_label
    action_button = row._action_button

    row.set_row(
        module.QueueJobRowView(
            job_id="job-1",
            title="Workflow #1",
            subtitle="Completed - 1 output",
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
        )
    )

    assert row._title_label is title_label
    assert row._subtitle_label is subtitle_label
    assert row._action_button is action_button
    assert row._title_label.text == "Workflow #1"
    assert row._subtitle_label.text == "Completed - 1 output"
    assert row._action_button.tooltip == "Remove job"
    assert row.mouse_tracking is False


def test_queue_row_drag_starts_from_body_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending row body children should emit pointer events for container drag."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Next",
        status="Pending",
        action="cancel",
        interaction_role="draggable",
        pending_visual_index=0,
        pending_dispatch_index=0,
    )
    row = module.GenerationQueueItemRow(row_view)
    emitted: list[tuple[str, str, int]] = []
    row.bodyPressed.connect(
        lambda job_id, position: emitted.append(("press", job_id, position.y()))
    )
    row.bodyMoved.connect(
        lambda job_id, position: emitted.append(("move", job_id, position.y()))
    )
    body_child = row._body_drag_targets[0]

    row.eventFilter(body_child, _MouseEvent(module.QEvent.Type.MouseButtonPress, 0))
    consumed = row.eventFilter(
        body_child,
        _MouseEvent(module.QEvent.Type.MouseMove, 14),
    )

    assert consumed is False
    assert emitted == [("press", "job-1", 0), ("move", "job-1", 14)]
    row.set_dragging(True)
    consumed_while_dragging = row.eventFilter(
        body_child,
        _MouseEvent(module.QEvent.Type.MouseMove, 18),
    )
    assert consumed_while_dragging is True


def test_queue_row_drag_does_not_start_from_non_draggable_body_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active and resolved body children should not start drag gestures."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_item_row"
    )
    row_view = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Running",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )
    row = module.GenerationQueueItemRow(row_view)
    emitted: list[str] = []
    row.bodyPressed.connect(lambda job_id, _position: emitted.append(job_id))
    body_child = row._body_drag_targets[0]

    row.eventFilter(body_child, _MouseEvent(module.QEvent.Type.MouseButtonPress, 0))
    consumed = row.eventFilter(
        body_child,
        _MouseEvent(module.QEvent.Type.MouseMove, 14),
    )

    assert consumed is False
    assert emitted == []


def test_queue_drag_target_calculation_uses_pending_section_only() -> None:
    """Drag target math should use visible pending rows only."""

    geometries = (
        PendingRowGeometry("a", 0, 46, 86),
        PendingRowGeometry("b", 1, 160, 200),
    )

    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            20,
        )
        == 0
    )
    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            80,
        )
        == 1
    )
    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            190,
        )
        == 2
    )
    assert (
        pending_drop_insertion_index_for_y(
            geometries,
            280,
        )
        is None
    )


def test_queue_drag_service_target_suppresses_noop_drops() -> None:
    """Dispatch insertion positions should convert to service target indexes."""

    assert (
        service_target_index_for_drop(
            source_pending_index=2,
            insertion_index=0,
            pending_count=3,
        )
        == 0
    )
    assert (
        service_target_index_for_drop(
            source_pending_index=0,
            insertion_index=3,
            pending_count=3,
        )
        == 2
    )
    assert (
        service_target_index_for_drop(
            source_pending_index=1,
            insertion_index=1,
            pending_count=3,
        )
        is None
    )
    assert (
        service_target_index_for_drop(
            source_pending_index=1,
            insertion_index=2,
            pending_count=3,
        )
        is None
    )


def test_queue_drag_converts_visual_slots_to_dispatch_slots() -> None:
    """Visual bottom-to-top drop slots should become dispatch insertion slots."""

    assert dispatch_insertion_index_from_visual(0, 3) == 3
    assert dispatch_insertion_index_from_visual(1, 3) == 2
    assert dispatch_insertion_index_from_visual(2, 3) == 1
    assert dispatch_insertion_index_from_visual(3, 3) == 0
    assert dispatch_insertion_index_from_visual(-1, 3) == 3
    assert dispatch_insertion_index_from_visual(4, 3) == 0

    top_visual_source_dispatch_index = 2
    bottom_visual_insertion_index = 3
    assert (
        service_target_index_for_drop(
            source_pending_index=top_visual_source_dispatch_index,
            insertion_index=dispatch_insertion_index_from_visual(
                bottom_visual_insertion_index,
                3,
            ),
            pending_count=3,
        )
        == 0
    )

    bottom_visual_source_dispatch_index = 0
    top_visual_insertion_index = 0
    assert (
        service_target_index_for_drop(
            source_pending_index=bottom_visual_source_dispatch_index,
            insertion_index=dispatch_insertion_index_from_visual(
                top_visual_insertion_index,
                3,
            ),
            pending_count=3,
        )
        == 2
    )


def test_queue_drag_target_math_ignores_non_pending_rows() -> None:
    """Pending geometry alone should determine legal drop slots."""

    geometries = (
        PendingRowGeometry("pending-a", 0, 10, 50),
        PendingRowGeometry("pending-b", 1, 60, 100),
    )

    assert pending_drop_insertion_index_for_y(geometries, 120) == 2
    assert pending_drop_insertion_index_for_y(geometries, 180) is None
    assert (
        service_target_index_for_drop(
            source_pending_index=0,
            insertion_index=2,
            pending_count=2,
        )
        == 1
    )


def test_queue_rows_view_reuses_widgets_for_progress_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows view should update existing job widgets instead of recreating them."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    row = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Running",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows((row,))
    first_widget = view._row_widgets_by_job_id["job-1"]

    view.set_rows(
        (
            module.QueueJobRowView(
                job_id="job-1",
                title="Workflow #1",
                subtitle="42% complete",
                status="Running",
                action="cancel",
                visual_role="active",
                interaction_role="none",
            ),
        )
    )

    assert view._row_widgets_by_job_id["job-1"] is first_widget
    assert first_widget.deleted is False
    assert first_widget._subtitle_label.text == "42% complete"


def test_queue_rows_view_updates_one_row_without_rebuilding_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental updates should keep widgets and stored row models current."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    original = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Running",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )
    updated = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="42% complete",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows((original,))
    first_widget = view._row_widgets_by_job_id["job-1"]
    original_layout_items = list(view._layout.items)

    assert view.update_row(updated) is True

    assert view._row_widgets_by_job_id["job-1"] is first_widget
    assert list(view._layout.items) == original_layout_items
    assert view._rows == (updated,)
    assert view._display_items == (updated,)
    assert view._row_by_job_id("job-1") == updated
    assert first_widget._subtitle_label.text == "42% complete"


def test_queue_rows_view_rejects_incremental_placement_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Placement-sensitive row changes should fall back to full reconciliation."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    original = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Running",
        status="Running",
        action="cancel",
        visual_role="active",
        interaction_role="none",
    )
    placement_changed = module.QueueJobRowView(
        job_id="job-1",
        title="Workflow #1",
        subtitle="Next",
        status="Waiting",
        action="cancel",
        visual_role="pending",
        interaction_role="draggable",
        pending_visual_index=0,
        pending_dispatch_index=0,
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows((original,))

    assert view.update_row(placement_changed) is False
    assert view._rows == (original,)
    assert view._row_by_job_id("job-1") == original


def test_queue_rows_view_deletes_only_removed_job_widgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows view reconciliation should delete stale rows and keep survivors."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    first_row = module.QueueJobRowView(
        job_id="a",
        title="Workflow A #1",
        subtitle="Waiting - 1 ahead",
        status="Pending",
        action="cancel",
        interaction_role="draggable",
        pending_visual_index=0,
        pending_dispatch_index=1,
    )
    second_row = module.QueueJobRowView(
        job_id="b",
        title="Workflow B #2",
        subtitle="Next",
        status="Pending",
        action="cancel",
        interaction_role="draggable",
        pending_visual_index=1,
        pending_dispatch_index=0,
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows((first_row, second_row))
    first_widget = view._row_widgets_by_job_id["a"]
    second_widget = view._row_widgets_by_job_id["b"]

    view.set_rows((second_row,))

    assert first_widget.deleted is True
    assert view._row_widgets_by_job_id["b"] is second_widget
    assert second_widget.deleted is False


def test_queue_rows_view_pending_drag_emits_move_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Container-owned drag should emit a service move request for pending rows."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    rows = (
        module.QueueJobRowView(
            job_id="a",
            title="Workflow A #1",
            subtitle="Waiting - 1 ahead",
            status="Pending",
            action="cancel",
            interaction_role="draggable",
            pending_visual_index=0,
            pending_dispatch_index=1,
        ),
        module.QueueJobRowView(
            job_id="b",
            title="Workflow B #2",
            subtitle="Next",
            status="Pending",
            action="cancel",
            interaction_role="draggable",
            pending_visual_index=1,
            pending_dispatch_index=0,
        ),
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows(rows)
    view._row_widgets_by_job_id["a"].widget_y = 0
    view._row_widgets_by_job_id["b"].widget_y = 50
    emitted: list[tuple[str, int]] = []
    view.moveRequested.connect(
        lambda job_id, target_index: emitted.append((job_id, target_index))
    )

    view._handle_body_pressed("a", _point(10))
    view._handle_body_moved("a", _point(100))
    assert view._drop_placeholder is not None
    assert view._drag_proxy is not None
    assert view._row_widgets_by_job_id["a"].visible is False
    view._handle_body_released("a", _point(100))

    assert emitted == [("a", 0)]
    assert view._drop_placeholder is None
    assert view._drag_proxy is None
    assert view._row_widgets_by_job_id["a"].visible is True


def test_queue_rows_view_ignores_active_and_resolved_drag_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only pending rows should start container-owned reorder gestures."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    rows = (
        module.QueueJobRowView(
            job_id="active",
            title="Workflow A #1",
            subtitle="Running",
            status="Running",
            action="cancel",
            visual_role="active",
            interaction_role="none",
        ),
        module.QueueJobRowView(
            job_id="done",
            title="Workflow B #2",
            subtitle="Completed - 1 output",
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
        ),
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows(rows)
    emitted: list[tuple[str, int]] = []
    view.moveRequested.connect(
        lambda job_id, target_index: emitted.append((job_id, target_index))
    )

    view._handle_body_pressed("active", _point(0))
    view._handle_body_moved("active", _point(40))
    view._handle_body_released("active", _point(40))
    view._handle_body_pressed("done", _point(50))
    view._handle_body_moved("done", _point(0))
    view._handle_body_released("done", _point(0))

    assert emitted == []
    assert view._drag_state is None


def test_queue_rows_view_placeholder_adds_physical_drop_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drag target placeholders should occupy real layout space."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    view.set_rows(
        (
            module.QueueJobRowView(
                job_id="a",
                title="Workflow A #1",
                subtitle="Next",
                status="Pending",
                action="cancel",
                interaction_role="draggable",
                pending_visual_index=0,
                pending_dispatch_index=0,
            ),
        )
    )

    view._handle_body_pressed("a", _point(10))
    view._handle_body_moved("a", _point(30))

    assert view._drop_placeholder is not None
    assert view._drop_placeholder in view._layout.items


def test_queue_rows_view_trailing_pending_drop_stays_before_non_pending_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The final pending drop slot should not render below active or resolved rows."""

    _install_queue_row_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    view = module.GenerationQueueRowsView(surface_mode="panel")
    rows = (
        module.QueueJobRowView(
            job_id="pending",
            title="Workflow A #1",
            subtitle="Next",
            status="Pending",
            action="cancel",
            interaction_role="draggable",
            pending_visual_index=0,
            pending_dispatch_index=0,
        ),
        module.QueueJobRowView(
            job_id="active",
            title="Workflow B #2",
            subtitle="Running",
            status="Running",
            action="cancel",
            visual_role="active",
            interaction_role="none",
        ),
        module.QueueJobRowView(
            job_id="done",
            title="Workflow C #3",
            subtitle="Completed - 1 output",
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
        ),
    )
    view.set_rows(rows)

    view._handle_body_pressed("pending", _point(10))
    view._handle_body_moved("pending", _point(70))

    assert view._drop_placeholder is not None
    layout_items = view._layout.items
    placeholder_index = layout_items.index(view._drop_placeholder)
    active_index = layout_items.index(view._row_widgets_by_job_id["active"])
    resolved_index = layout_items.index(view._row_widgets_by_job_id["done"])
    assert placeholder_index < active_index
    assert placeholder_index < resolved_index


@_REAL_QT_XDIST_SKIP
def test_queue_rows_view_real_qt_pending_drag_emits_move_request() -> None:
    """Real Qt mouse drag should reorder pending rows through the shared signal."""

    _clear_gui_stubs_for_real_qt()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    app = QApplication.instance() or QApplication([])
    view = module.GenerationQueueRowsView(surface_mode="panel")
    rows = (
        module.QueueJobRowView(
            job_id="a",
            title="Workflow A #1",
            subtitle="Waiting - 1 ahead",
            status="Pending",
            action="cancel",
            interaction_role="draggable",
            pending_visual_index=0,
            pending_dispatch_index=1,
        ),
        module.QueueJobRowView(
            job_id="b",
            title="Workflow B #2",
            subtitle="Next",
            status="Pending",
            action="cancel",
            interaction_role="draggable",
            pending_visual_index=1,
            pending_dispatch_index=0,
        ),
    )
    emitted: list[tuple[str, int]] = []
    view.moveRequested.connect(
        lambda job_id, target_index: emitted.append((job_id, target_index))
    )
    view.resize(360, 180)
    view.set_rows(rows)
    view.show()
    app.processEvents()
    source = view._row_widgets_by_job_id["b"]
    source_center = QPoint(12, max(1, source.height() // 2))
    target_in_parent = QPoint(12, 0)
    target_in_source = source.mapFromParent(target_in_parent)

    QTest.mousePress(source, Qt.MouseButton.LeftButton, pos=source_center)
    QTest.mouseMove(source, target_in_source, 10)
    app.processEvents()

    assert view._drop_placeholder is not None
    assert view._drag_proxy is not None

    QTest.mouseRelease(source, Qt.MouseButton.LeftButton, pos=target_in_source)
    QTest.qWait(180)
    app.processEvents()

    assert emitted == [("b", 1)]
    view.close()
    view.deleteLater()
    app.processEvents()


@_REAL_QT_XDIST_SKIP
def test_queue_rows_view_real_qt_blocks_non_pending_drags() -> None:
    """Active and resolved rows should not enter real Qt drag state."""

    _clear_gui_stubs_for_real_qt()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    app = QApplication.instance() or QApplication([])
    view = module.GenerationQueueRowsView(surface_mode="panel")
    rows = (
        module.QueueJobRowView(
            job_id="active",
            title="Workflow A #1",
            subtitle="Running",
            status="Running",
            action="cancel",
            visual_role="active",
            interaction_role="none",
        ),
        module.QueueJobRowView(
            job_id="done",
            title="Workflow B #2",
            subtitle="Completed - 1 output",
            status="Completed",
            action="remove",
            visual_role="resolved",
            interaction_role="context",
        ),
    )
    emitted: list[tuple[str, int]] = []
    view.moveRequested.connect(
        lambda job_id, target_index: emitted.append((job_id, target_index))
    )
    view.resize(360, 180)
    view.set_rows(rows)
    view.show()
    app.processEvents()

    for job_id in ("active", "done"):
        row = view._row_widgets_by_job_id[job_id]
        QTest.mousePress(row, Qt.MouseButton.LeftButton, pos=QPoint(12, 12))
        QTest.mouseMove(row, QPoint(12, -30), 10)
        QTest.mouseRelease(row, Qt.MouseButton.LeftButton, pos=QPoint(12, -30))

    assert emitted == []
    assert view._drag_state is None
    assert view._drop_placeholder is None
    view.close()
    view.deleteLater()
    app.processEvents()


@_REAL_QT_XDIST_SKIP
def test_queue_rows_view_real_qt_action_button_does_not_start_drag() -> None:
    """Clicking the row action button should not prime a reorder drag."""

    _clear_gui_stubs_for_real_qt()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    module = importlib.import_module(
        "substitute.presentation.generation.queue_rows_view"
    )
    app = QApplication.instance() or QApplication([])
    view = module.GenerationQueueRowsView(surface_mode="panel")
    row = module.QueueJobRowView(
        job_id="a",
        title="Workflow A #1",
        subtitle="Next",
        status="Pending",
        action="cancel",
        interaction_role="draggable",
        pending_visual_index=0,
        pending_dispatch_index=0,
    )
    cancelled: list[str] = []
    view.cancelRequested.connect(cancelled.append)
    view.resize(360, 100)
    view.set_rows((row,))
    view.show()
    app.processEvents()
    action_button = view._row_widgets_by_job_id["a"]._action_button

    QTest.mouseClick(action_button, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert cancelled == ["a"]
    assert view._drag_state is None
    assert view._drop_placeholder is None
    view.close()
    view.deleteLater()
    app.processEvents()


class _ScrollArea(_Widget):
    """Scroll area stand-in for dropdown tests."""

    created: list["_ScrollArea"] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Record created qfluent scroll areas."""

        super().__init__(*_args, **_kwargs)
        self.scrollDelagate = _FakeSmoothScrollDelegate()
        self.transparent_background_enabled = False
        self.widget_was_set_before_transparency = False
        _ScrollArea.created.append(self)

    def setWidgetResizable(self, _value: bool) -> None:
        """Accept widget-resizable assignment."""

    def setFrameShape(self, _shape: object) -> None:
        """Accept frame-shape assignment."""

    def setHorizontalScrollBarPolicy(self, _policy: object) -> None:
        """Accept scrollbar-policy assignment."""

    def setWidget(self, widget: object) -> None:
        """Record contained widget."""

        self.widget = widget

    def enableTransparentBackground(self) -> None:
        """Record qfluent transparent background setup."""

        self.transparent_background_enabled = True
        self.widget_was_set_before_transparency = hasattr(self, "widget")


class _FakeSmoothScroll:
    """Smooth-scroll test double recording requested modes."""

    def __init__(self) -> None:
        """Initialize a fake QFluent smooth-scroll engine."""

        self.mode: object | None = None

    def setSmoothMode(self, mode: object) -> None:  # noqa: N802
        """Record the mode assigned by the shared scroll policy."""

        self.mode = mode


class _FakeSmoothScrollBar:
    """QFluent scrollbar test double recording animation duration."""

    def __init__(self) -> None:
        """Initialize a fake animated scrollbar."""

        self.duration = 500

    def setScrollAnimation(self, duration: int) -> None:  # noqa: N802
        """Record the animation duration assigned by the scroll policy."""

        self.duration = duration


class _FakeSmoothScrollDelegate:
    """QFluent scroll delegate test double for queue widget stubs."""

    def __init__(self) -> None:
        """Build fake smooth-scroll engines and animated scrollbar chrome."""

        self.useAni = True
        self.verticalSmoothScroll = _FakeSmoothScroll()
        self.horizonSmoothScroll = _FakeSmoothScroll()
        self.vScrollBar = _FakeSmoothScrollBar()
        self.hScrollBar = _FakeSmoothScrollBar()


class _FakeFlyout:
    """Flyout stand-in recording visibility and close events."""

    created: list["_FakeFlyout"] = []

    def __init__(self, view: object) -> None:
        """Create one visible flyout."""

        self.view = view
        self.closed = _Signal()
        self._visible = True
        _FakeFlyout.created.append(self)

    @classmethod
    def make(cls, view: object, *_args: object) -> "_FakeFlyout":
        """Create one fake flyout as qfluent would."""

        return cls(view)

    def isVisible(self) -> bool:
        """Return current visibility."""

        return self._visible

    def close(self) -> None:
        """Close and emit the closed signal."""

        self._visible = False
        self.closed.emit()


def _install_dropdown_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install PySide and qfluent stubs needed by the dropdown module."""

    importlib.import_module("sugarsubstitute_shared.presentation.widgets.scrolling")
    shared_localization = importlib.import_module(
        "sugarsubstitute_shared.presentation.localization"
    )
    monkeypatch.setattr(
        shared_localization,
        "set_localized_tooltip",
        lambda target, text, *arguments: target.setToolTip(str(text)),
    )

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        NoTextInteraction="no-text",
        ArrowCursor="arrow",
        OpenHandCursor="open-hand",
        ClosedHandCursor="closed-hand",
        PointingHandCursor="pointing",
        AlignRight=1,
        AlignVCenter=2,
        AlignCenter=4,
        AlignLeft=8,
        ScrollBarAlwaysOff="off",
    )
    qtcore.QEvent = _QEvent
    qtcore.QObject = _QObject
    qtcore.QPropertyAnimation = _QPropertyAnimation
    qtcore.QRect = _QRect
    qtcore.QRectF = _QRectF
    qtcore.QSize = _QSize
    qtcore.Property = _Property
    qtcore.Signal = _SignalDescriptor
    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QPixmap = _Pixmap
    qtgui.QColor = _QColor
    qtgui.QPainter = _QPainter
    qtgui.QPainterPath = _QPainterPath
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QFrame = type("QFrame", (_Widget,), {"NoFrame": "no-frame"})
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget

    qfw = types.ModuleType("qfluentwidgets")
    qfw.FluentIconBase = _FluentIconBase
    qfw.FluentIcon = types.SimpleNamespace(CLOSE=object(), DELETE=object())
    qfw.Theme = types.SimpleNamespace(AUTO="auto")
    qfw.getIconColor = lambda _theme: "black"
    qfw.isDarkTheme = lambda: True
    qfw.ScrollArea = _ScrollArea
    qfw.TransparentToolButton = _Button
    qfw_common = types.ModuleType("qfluentwidgets.common")
    qfw_config = types.ModuleType("qfluentwidgets.common.config")
    qfw_config.qconfig = None
    qfw_style_sheet = types.ModuleType("qfluentwidgets.common.style_sheet")
    qfw_style_sheet.isDarkTheme = lambda: True
    qfw_style_sheet.themeColor = lambda: _QColor("#009FAA")
    material = types.ModuleType("qfluentwidgets.components.material")
    material.AcrylicFlyout = _FakeFlyout
    material.AcrylicFlyoutViewBase = _Widget
    flyout = types.ModuleType("qfluentwidgets.components.widgets.flyout")
    flyout.FlyoutAnimationType = types.SimpleNamespace(DROP_DOWN="drop-down")
    localization = types.ModuleType("substitute.presentation.localization")
    localization.LocalizedBodyLabel = _Widget
    localization.LocalizedCaptionLabel = _Widget
    localization.LocalizedStrongBodyLabel = _Widget
    cursor_tooltip = types.ModuleType(
        "sugarsubstitute_shared.presentation.fluent_tooltips"
    )

    class _CursorToolTipFilter:
        """Record cursor-tooltip filter construction for dropdown tests."""

        def __init__(
            self,
            owner: object,
            *,
            show_delay_ms: int,
            watched_widgets: tuple[object, ...],
        ) -> None:
            """Store construction details."""

            self._owner = owner
            self._show_delay_ms = show_delay_ms
            self.watched_widgets = watched_widgets

    def _install_cursor_tooltip_filter(
        owner: object,
        *watched_widgets: object,
        show_delay_ms: int = 300,
        **_kwargs: object,
    ) -> _CursorToolTipFilter:
        """Install one test cursor-tooltip filter on watched widgets."""

        tooltip_filter = _CursorToolTipFilter(
            owner,
            show_delay_ms=show_delay_ms,
            watched_widgets=watched_widgets,
        )
        for widget in watched_widgets or (owner,):
            widget.installEventFilter(tooltip_filter)
        return tooltip_filter

    cursor_tooltip.FluentToolTipFilter = _CursorToolTipFilter
    cursor_tooltip.ensure_fluent_tooltip_filter = _install_cursor_tooltip_filter
    cursor_tooltip.set_fluent_tooltip_text = lambda target, text: target.setToolTip(
        text
    )
    shiboken = types.ModuleType("shiboken6")
    shiboken.isValid = lambda _obj: True

    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "shiboken6", shiboken)
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.localization",
        localization,
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.common", qfw_common)
    monkeypatch.setitem(sys.modules, "qfluentwidgets.common.config", qfw_config)
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.common.style_sheet",
        qfw_style_sheet,
    )
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.components",
        types.ModuleType("qfluentwidgets.components"),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.components.material", material)
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.components.widgets",
        types.ModuleType("qfluentwidgets.components.widgets"),
    )
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.components.widgets.flyout",
        flyout,
    )
    monkeypatch.setitem(
        sys.modules,
        "sugarsubstitute_shared.presentation.fluent_tooltips",
        cursor_tooltip,
    )
    for module_name in (
        "substitute.presentation.generation.queue_panel",
        "substitute.presentation.generation.queue_dropdown",
        "substitute.presentation.generation.queue_item_row",
        "substitute.presentation.generation.queue_rows_view",
        "substitute.presentation.resources.app_icon",
        "sugarsubstitute_shared.presentation.fluent_tooltips",
        "substitute.presentation.widgets.row_interaction_feedback",
        "substitute.presentation.shell.chrome_style",
    ):
        if module_name != "sugarsubstitute_shared.presentation.fluent_tooltips":
            sys.modules.pop(module_name, None)


def _assert_fake_qfluent_smoothing_disabled(scroll_area: _ScrollArea) -> None:
    """Assert the queue scroll area received the no-smooth QFluent policy."""

    scroll_delegate = scroll_area.scrollDelagate
    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.mode is not None
    assert scroll_delegate.horizonSmoothScroll.mode is not None
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0


class _FakeQueueService:
    """Queue service stand-in for dropdown intent routing tests."""

    def __init__(
        self,
        queue_job: GenerationQueueJob | None = None,
        *,
        queue_jobs: tuple[GenerationQueueJob, ...] | None = None,
    ) -> None:
        """Store initial queue state and call capture."""

        self._queue_jobs = (
            queue_jobs
            if queue_jobs is not None
            else (() if queue_job is None else (queue_job,))
        )
        self.cancelled: list[str] = []
        self.removed: list[str] = []
        self.moved: list[tuple[str, int]] = []
        self.observers: list[Callable[[GenerationQueueStateChange], None]] = []

    def add_observer(
        self,
        observer: Callable[[GenerationQueueStateChange], None],
    ) -> None:
        """Record and immediately publish initial queue state."""

        self.observers.append(observer)
        observer(
            GenerationQueueStateChange(
                jobs=self._queue_jobs,
                change_kind="structural",
            )
        )

    def remove_observer(
        self,
        observer: Callable[[GenerationQueueStateChange], None],
    ) -> None:
        """Remove a previously registered queue observer."""

        self.observers = [
            registered for registered in self.observers if registered != observer
        ]

    def cancel_job(self, job_id: str) -> None:
        """Record one cancel request."""

        self.cancelled.append(job_id)

    def remove_terminal_job(self, job_id: str) -> None:
        """Record one terminal-row remove request."""

        self.removed.append(job_id)

    def move_pending_job(self, job_id: str, target_index: int) -> None:
        """Record one pending-row move request."""

        self.moved.append((job_id, target_index))


def test_queue_dropdown_toggles_and_routes_cancel_intents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue dropdown should open, close, and route row cancel intents to the service."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_dropdown"
    )
    queue_job = _job("a", status="pending")
    service = _FakeQueueService(queue_job)
    dropdown = module.GenerationQueueDropdown(service, parent=_Widget())

    dropdown.toggle_for(_Widget())
    assert dropdown.is_visible() is True
    cast(Any, _FakeFlyout.created[-1].view).cancelRequested.emit("a")
    cast(Any, _FakeFlyout.created[-1].view).removeRequested.emit("a")
    cast(Any, _FakeFlyout.created[-1].view).moveRequested.emit("a", 0)
    dropdown.toggle_for(_Widget())

    assert service.cancelled == ["a"]
    assert service.removed == ["a"]
    assert service.moved == [("a", 0)]
    assert dropdown.is_visible() is False
    assert service.observers
    _assert_fake_qfluent_smoothing_disabled(_ScrollArea.created[-1])
    assert _ScrollArea.created[-1].transparent_background_enabled is True
    assert _ScrollArea.created[-1].widget_was_set_before_transparency is True
    assert "transparent" in cast(Any, _ScrollArea.created[-1].widget).style
    dropdown.dispose()
    assert service.observers == []


def test_queue_panel_routes_shared_row_intents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue panel should route shared rows-view intents to the queue service."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module("substitute.presentation.generation.queue_panel")
    queue_job = _job("a", status="pending")
    service = _FakeQueueService(queue_job)
    opened: list[str] = []
    panel = module.GenerationQueuePanel(
        service,
        open_snapshot_requested=lambda job_id: opened.append(job_id),
        parent=_Widget(),
    )

    panel._rows_view.cancelRequested.emit("a")
    panel._rows_view.removeRequested.emit("a")
    panel._rows_view.moveRequested.emit("a", 0)
    panel._rows_view.openSnapshotRequested.emit("a")

    assert service.cancelled == ["a"]
    assert service.removed == ["a"]
    assert service.moved == [("a", 0)]
    assert opened == ["a"]
    _assert_fake_qfluent_smoothing_disabled(cast(Any, panel)._scroll_area)
    panel.dispose()
    assert service.observers == []


def test_queue_panel_header_exposes_hide_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue panel header should pair the title with a right-aligned hide button."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module("substitute.presentation.generation.queue_panel")
    app_icon = importlib.import_module("substitute.presentation.resources.app_icon")
    service = _FakeQueueService()
    panel = module.GenerationQueuePanel(service, parent=_Widget())
    header = cast(Any, panel)._header
    header_layout = cast(_Layout, header.layout())
    hide_button = cast(Any, panel)._hide_panel_button

    assert cast(_Layout, panel.layout()).items[0] is header
    assert header_layout.items[0].object_name == "GenerationQueuePanelTitle"
    assert header_layout.items[1] is None
    assert header_layout.items[2] is hide_button
    assert hide_button.object_name == "GenerationQueuePanelHideButton"
    assert hide_button.icon is app_icon.AppIcon.PANEL_RIGHT_20_FILLED
    assert hide_button.tooltip == "Hide full queue panel"
    assert hide_button.icon_size is not None


def test_queue_panel_header_counts_only_pending_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expanded queue panel title should match the pending titlebar queue count."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module("substitute.presentation.generation.queue_panel")
    service = _FakeQueueService(
        queue_jobs=(
            _job("pending", status="pending"),
            _job("running", status="running"),
            _job("completed", status="completed"),
            _job("cancelled", status="cancelled"),
        ),
    )
    panel = module.GenerationQueuePanel(service, parent=_Widget())

    assert cast(Any, panel)._title_label.text == "Generation Queue :: 1 Pending Jobs"


def test_queue_panel_hide_button_emits_hide_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue panel hide button should emit a shell-owned hide intent."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module("substitute.presentation.generation.queue_panel")
    service = _FakeQueueService()
    panel = module.GenerationQueuePanel(service, parent=_Widget())
    hide_requests: list[bool] = []
    panel.hideRequested.connect(lambda: hide_requests.append(True))

    cast(Any, panel)._hide_panel_button.clicked.emit()

    assert hide_requests == [True]


def test_queue_panel_empty_state_keeps_header_top_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue panel empty state should center inside content below the header."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module("substitute.presentation.generation.queue_panel")
    service = _FakeQueueService()
    panel = module.GenerationQueuePanel(service, parent=_Widget())
    layout = cast(_Layout, panel.layout())
    header = cast(Any, panel)._header
    empty_state = cast(Any, panel)._empty_state
    empty_layout = cast(_Layout, empty_state.layout())

    assert layout.items[0] is header
    assert layout.items[1] is empty_state
    assert layout.stretches[:3] == [0, 1, 1]
    assert empty_state.isVisible() is True
    assert cast(Any, panel)._scroll_area.isVisible() is False
    assert empty_layout.items == [None, cast(Any, panel)._empty_label, None]
    assert empty_layout.stretches == [1, 0, 1]
    assert cast(Any, panel)._empty_label.minimum_height == 88


def test_queue_dropdown_empty_state_uses_same_content_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue dropdown empty state should center inside content below the header."""

    _install_dropdown_stubs(monkeypatch)
    module = importlib.import_module(
        "substitute.presentation.generation.queue_dropdown"
    )
    view = module.GenerationQueueDropdownView(_Widget())
    layout = cast(_Layout, view.layout())
    empty_state = cast(Any, view)._empty_state
    empty_layout = cast(_Layout, empty_state.layout())

    assert layout.items[0].object_name == "GenerationQueueTitle"
    assert layout.items[1] is empty_state
    assert layout.stretches[:3] == [0, 1, 1]
    assert empty_state.isVisible() is True
    assert cast(Any, view)._scroll_area.isVisible() is False
    assert empty_layout.items == [None, cast(Any, view)._empty_label, None]
    assert empty_layout.stretches == [1, 0, 1]
    assert cast(Any, view)._empty_label.minimum_height == 88
