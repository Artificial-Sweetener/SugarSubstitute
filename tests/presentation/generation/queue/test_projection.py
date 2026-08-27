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

"""Verify pure generation queue display projection."""

from __future__ import annotations

from datetime import datetime, timezone

from substitute.presentation.generation.queue_counts import (
    pending_generation_queue_job_count,
)
from substitute.presentation.generation.queue_list_view import (
    QueueBucketDividerView,
    QueueJobRowView,
    queue_job_display_items,
    queue_job_row_views,
)
from tests.presentation.generation.queue.support import queue_job


def test_queue_display_items_render_final_scene_batch_state() -> None:
    """A single final observer state should still render every scene job."""

    jobs = (
        queue_job(
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
        queue_job(
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
        queue_job(
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


def test_queue_job_row_views_show_projected_and_committed_numbers() -> None:
    """Rows should display projected pending and committed active/resolved numbers."""

    rows = queue_job_row_views(
        (
            queue_job(
                "a",
                status="pending",
                projected_output_run_number=7,
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            ),
            queue_job(
                "b",
                status="running",
                prompt_id="prompt-b-123456",
                output_run_number=8,
                progress_percent=62.4,
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            ),
            queue_job(
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
            queue_job(
                "completed",
                status="completed",
                execution_duration_ms=308000.0,
            ),
            queue_job(
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

    rows = queue_job_row_views((queue_job("a", status="pending"),))

    assert rows[0].title == "Workflow a #001"
    assert rows[0].subtitle == "Next"


def test_queue_job_row_views_show_pending_bottom_to_top_order() -> None:
    """Pending rows should display latest first while subtitles follow dispatch order."""

    rows = queue_job_row_views(
        (
            queue_job(
                "a",
                status="pending",
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                workflow_name="Shared",
            ),
            queue_job(
                "b",
                status="pending",
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
                workflow_name="Shared",
            ),
            queue_job(
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
            queue_job("a", status="pending", workflow_name="Shared"),
            queue_job("b", status="pending", workflow_name="Shared"),
        )
    )
    reordered_rows = queue_job_row_views(
        (
            queue_job("b", status="pending", workflow_name="Shared"),
            queue_job("a", status="pending", workflow_name="Shared"),
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
            queue_job("a", status="pending", workflow_name="Shared"),
            queue_job("b", status="pending", workflow_name="Other"),
            queue_job("c", status="pending", workflow_name="Shared"),
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
            queue_job(
                "a",
                status="pending",
                workflow_name="Shared",
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
            queue_job(
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
            queue_job(
                "today",
                status="pending",
                workflow_name="Workflow",
                projected_output_run_number=1,
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
            queue_job(
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
            queue_job(
                "first",
                status="pending",
                workflow_name="Workflow",
                projected_output_run_number=1,
                projected_output_bucket_key="bucket-today",
                projected_output_bucket_label="2026-05-12",
            ),
            queue_job(
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
            queue_job(
                "active",
                status="running",
                output_run_number=22,
                workflow_name="Shared",
            ),
            queue_job("pending", status="pending", workflow_name="Shared"),
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
            queue_job(
                "active",
                status="running",
                created_at=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
            ),
            queue_job(
                "next",
                status="pending",
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            ),
            queue_job(
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
