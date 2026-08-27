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

"""Verify generation queue status and diagnostic projection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from substitute.presentation.generation.queue_list_view import (
    queue_job_row_views,
    should_show_pending_resolved_separator,
)
from tests.presentation.generation.queue.support import queue_job


def test_queue_job_row_views_show_cancelled_output_counts_only() -> None:
    """Keep saved counts on cancelled rows while completed rows stay compact."""

    rows = queue_job_row_views(
        (
            queue_job("completed-one", status="completed", output_count=1),
            queue_job("cancelled-none", status="cancelled", output_count=0),
            queue_job("cancelled-one", status="cancelled", output_count=1),
        )
    )

    subtitles_by_job_id = {row.job_id: row.subtitle for row in rows}
    assert subtitles_by_job_id["completed-one"] == "Completed"
    assert subtitles_by_job_id["cancelled-none"] == "Cancelled - No outputs saved"
    assert subtitles_by_job_id["cancelled-one"] == "Cancelled - 1 output saved"


def test_queue_job_row_views_show_failure_summary_and_tooltip_detail() -> None:
    """Show compact failure summaries while preserving raw tooltip details."""

    rows = queue_job_row_views(
        (
            queue_job(
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
    """Bound visible failure reasons while preserving complete diagnostics."""

    long_summary = (
        "Backend produced an extremely verbose generation failure reason " * 4
    )
    failure_message = "Execution failed while running the prompt."
    failure_detail = "Traceback details with many internal frames."

    rows = queue_job_row_views(
        (
            queue_job(
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
    """Bound raw fallback reasons while retaining the full source in the tooltip."""

    failure_message = (
        "A very long unclassified generation failure continued with enough detail "
        "to overflow a compact queue row if rendered directly."
    )

    rows = queue_job_row_views(
        (
            queue_job(
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
    """Expose prompt previews independently from diagnostic tooltips."""

    rows = queue_job_row_views(
        (
            queue_job(
                "a",
                status="pending",
                positive_prompt_preview="fox in moonlight",
            ),
            queue_job("b", status="pending"),
        )
    )

    by_job_id = {row.job_id: row for row in rows}
    assert by_job_id["a"].prompt_tooltip == "fox in moonlight"
    assert by_job_id["a"].tooltip is None
    assert by_job_id["b"].prompt_tooltip is None


def test_queue_job_row_views_summarize_failed_raw_message() -> None:
    """Summarize a recognized raw failure when no durable summary exists."""

    rows = queue_job_row_views(
        (
            queue_job(
                "a",
                status="failed",
                failure_message="No module named 'xformers'",
            ),
        )
    )

    assert rows[0].subtitle == "Failed - Missing xformers"


def test_queue_job_row_views_expose_thumbnail_and_snapshot_open_state() -> None:
    """Expose snapshot actions and lazy thumbnail paths only for terminal rows."""

    rows = queue_job_row_views(
        (
            queue_job(
                "a",
                status="running",
                created_at=datetime(2026, 1, 1, 3, tzinfo=timezone.utc),
            ),
            queue_job(
                "b",
                status="completed",
                last_output_path=Path("out.png"),
                created_at=datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            ),
            queue_job(
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
    """Project active, draggable, and resolved interaction roles."""

    rows = queue_job_row_views(
        (
            queue_job("dispatching", status="dispatching"),
            queue_job("comfy", status="comfy_pending"),
            queue_job("running", status="running"),
            queue_job("pending", status="pending"),
            queue_job("completed", status="completed"),
            queue_job("failed", status="failed"),
            queue_job("cancelled", status="cancelled"),
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
    """Show the resolved separator only when no active row divides the sections."""

    assert should_show_pending_resolved_separator(
        queue_job_row_views(
            (
                queue_job("pending", status="pending"),
                queue_job("completed", status="completed"),
            )
        )
    )
    assert not should_show_pending_resolved_separator(
        queue_job_row_views(
            (
                queue_job("active", status="running"),
                queue_job("pending", status="pending"),
                queue_job("completed", status="completed"),
            )
        )
    )
