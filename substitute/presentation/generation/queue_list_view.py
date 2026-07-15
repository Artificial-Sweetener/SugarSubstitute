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

"""Convert generation queue jobs into compact presentation row models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from substitute.application.generation import (
    GenerationQueueJob,
    TERMINAL_GENERATION_JOB_STATUSES,
    format_generation_duration,
    summarize_generation_failure,
)

_STATUS_LABELS = {
    "pending": "Waiting",
    "dispatching": "Preparing",
    "comfy_pending": "Queued in Comfy",
    "running": "Running",
    "completed": "Completed",
    "failed": "Failed",
    "cancelled": "Cancelled",
}
_MAX_FAILURE_SUBTITLE_SUMMARY_LENGTH = 64

QueueJobRowAction = Literal["cancel", "remove"]
QueueJobVisualRole = Literal["active", "pending", "resolved"]
QueueJobInteractionRole = Literal["none", "draggable", "context"]
_ACTIVE_STATUSES = frozenset({"dispatching", "comfy_pending", "running"})


@dataclass(frozen=True)
class QueueJobRowView:
    """Describe one queue row without exposing widget state."""

    job_id: str
    title: str
    subtitle: str
    status: str
    action: QueueJobRowAction | None
    thumbnail_path: Path | None = None
    can_open_snapshot: bool = False
    tooltip: str | None = None
    prompt_tooltip: str | None = None
    visual_role: QueueJobVisualRole = "pending"
    interaction_role: QueueJobInteractionRole = "none"
    pending_visual_index: int | None = None
    pending_dispatch_index: int | None = None
    bucket_key: str | None = None
    bucket_label: str | None = None


@dataclass(frozen=True)
class QueueBucketDividerView:
    """Describe a passive output bucket divider in the generation queue."""

    key: str
    label: str


QueueDisplayItem = QueueBucketDividerView | QueueJobRowView


def queue_job_row_views(
    jobs: tuple[GenerationQueueJob, ...],
) -> tuple[QueueJobRowView, ...]:
    """Build row view models from the current generation queue state."""

    return queue_display_item_rows(queue_job_display_items(jobs))


def queue_job_row_view(
    jobs: tuple[GenerationQueueJob, ...],
    job_id: str,
) -> QueueJobRowView | None:
    """Return one row view model from the current generation queue state."""

    for row in queue_job_row_views(jobs):
        if row.job_id == job_id:
            return row
    return None


def queue_job_display_items(
    jobs: tuple[GenerationQueueJob, ...],
) -> tuple[QueueDisplayItem, ...]:
    """Build queue display items, including output bucket dividers."""

    rows: list[QueueJobRowView] = []
    pending_ahead_by_job_id = _pending_ahead_counts(jobs)
    pending_dispatch_index_by_job_id = _pending_dispatch_index_by_job_id(jobs)
    display_run_number_by_job_id = _display_run_numbers_by_job_id(jobs)
    display_jobs = _queue_display_jobs(jobs)
    pending_visual_index_by_job_id = _pending_visual_index_by_job_id(display_jobs)
    for job in display_jobs:
        status = _STATUS_LABELS.get(job.status, job.status)
        visual_role = _queue_visual_role(job)
        rows.append(
            QueueJobRowView(
                job_id=job.job_id,
                title=_queue_title(
                    job,
                    display_run_number_by_job_id.get(job.job_id),
                ),
                subtitle=_queue_subtitle(job, pending_ahead_by_job_id),
                status=status,
                action=(
                    "remove"
                    if job.status in TERMINAL_GENERATION_JOB_STATUSES
                    else "cancel"
                ),
                thumbnail_path=job.last_output_path,
                can_open_snapshot=job.status in {"completed", "cancelled"},
                tooltip=_queue_tooltip(job),
                prompt_tooltip=job.snapshot.positive_prompt_preview,
                visual_role=visual_role,
                interaction_role=_queue_interaction_role(visual_role),
                pending_visual_index=pending_visual_index_by_job_id.get(job.job_id),
                pending_dispatch_index=pending_dispatch_index_by_job_id.get(job.job_id),
                bucket_key=_queue_bucket_key(job),
                bucket_label=_queue_bucket_label(job),
            )
        )
    return _with_bucket_dividers(tuple(rows))


def queue_display_item_rows(
    items: tuple[QueueDisplayItem, ...],
) -> tuple[QueueJobRowView, ...]:
    """Return job rows from a mixed queue display item sequence."""

    return tuple(item for item in items if isinstance(item, QueueJobRowView))


def should_show_pending_resolved_separator(
    rows: tuple[QueueJobRowView, ...],
) -> bool:
    """Return whether a quiet pending/resolved separator should be shown."""

    has_active_row = any(row.visual_role == "active" for row in rows)
    has_pending_row = any(row.visual_role == "pending" for row in rows)
    has_resolved_row = any(row.visual_role == "resolved" for row in rows)
    return not has_active_row and has_pending_row and has_resolved_row


def _queue_title(
    job: GenerationQueueJob,
    display_run_number: int | None,
) -> str:
    """Return the row title with projected or committed output number."""

    if display_run_number is None:
        return job.snapshot.workflow_name
    return f"{job.snapshot.workflow_name} #{display_run_number:03d}"


def _display_run_numbers_by_job_id(
    jobs: tuple[GenerationQueueJob, ...],
) -> dict[str, int]:
    """Return projected or committed display output numbers keyed by job id."""

    next_number_by_bucket: dict[str, int] = {}
    numbers_by_job_id: dict[str, int] = {}
    for job in jobs:
        bucket_key = _queue_bucket_key(job) or job.snapshot.workflow_name
        if job.status == "pending":
            projected_number = job.projected_output_run_number
            if projected_number is None:
                projected_number = next_number_by_bucket.get(bucket_key, 1)
            numbers_by_job_id[job.job_id] = projected_number
            next_number_by_bucket[bucket_key] = max(
                next_number_by_bucket.get(bucket_key, 1),
                projected_number + 1,
            )
            continue
        if job.output_run_number is None:
            continue
        numbers_by_job_id[job.job_id] = job.output_run_number
        next_number_by_bucket[bucket_key] = max(
            next_number_by_bucket.get(bucket_key, 1),
            job.output_run_number + 1,
        )
    return numbers_by_job_id


def _with_bucket_dividers(
    rows: tuple[QueueJobRowView, ...],
) -> tuple[QueueDisplayItem, ...]:
    """Insert bucket dividers only when adjacent visible rows change bucket."""

    items: list[QueueDisplayItem] = []
    previous_bucket_key: str | None = None
    for row in rows:
        if (
            previous_bucket_key is not None
            and row.bucket_key is not None
            and row.bucket_label is not None
            and row.bucket_key != previous_bucket_key
        ):
            items.append(
                QueueBucketDividerView(key=row.bucket_key, label=row.bucket_label)
            )
        items.append(row)
        if row.bucket_key is not None:
            previous_bucket_key = row.bucket_key
    return tuple(items)


def _queue_bucket_key(job: GenerationQueueJob) -> str | None:
    """Return the committed or projected output bucket key for one job."""

    if job.status == "pending":
        return job.projected_output_bucket_key or job.output_bucket_key
    return job.output_bucket_key


def _queue_bucket_label(job: GenerationQueueJob) -> str | None:
    """Return the committed or projected output bucket label for one job."""

    if job.status == "pending":
        return job.projected_output_bucket_label or job.output_bucket_label
    return job.output_bucket_label


def _pending_ahead_counts(
    jobs: tuple[GenerationQueueJob, ...],
) -> dict[str, int]:
    """Return pending FIFO ahead counts keyed by job id."""

    pending_count = 0
    counts: dict[str, int] = {}
    for job in jobs:
        if job.status != "pending":
            continue
        counts[job.job_id] = pending_count
        pending_count += 1
    return counts


def _pending_dispatch_index_by_job_id(
    jobs: tuple[GenerationQueueJob, ...],
) -> dict[str, int]:
    """Return dispatch-order pending indexes keyed by job id."""

    indexes: dict[str, int] = {}
    for job in jobs:
        if job.status == "pending":
            indexes[job.job_id] = len(indexes)
    return indexes


def _pending_visual_index_by_job_id(
    display_jobs: tuple[GenerationQueueJob, ...],
) -> dict[str, int]:
    """Return top-to-bottom visual pending indexes keyed by job id."""

    indexes: dict[str, int] = {}
    for job in display_jobs:
        if job.status == "pending":
            indexes[job.job_id] = len(indexes)
    return indexes


def _queue_display_jobs(
    jobs: tuple[GenerationQueueJob, ...],
) -> tuple[GenerationQueueJob, ...]:
    """Return jobs ordered for queue display and reorder interactions."""

    pending_jobs = [job for job in jobs if job.status == "pending"]
    active_jobs = [job for job in jobs if job.status in _ACTIVE_STATUSES]
    resolved_jobs = sorted(
        (job for job in jobs if job.status in TERMINAL_GENERATION_JOB_STATUSES),
        key=lambda candidate: (
            candidate.completed_at or candidate.created_at,
            candidate.job_id,
        ),
        reverse=True,
    )
    return tuple(list(reversed(pending_jobs)) + active_jobs + resolved_jobs)


def _queue_visual_role(job: GenerationQueueJob) -> QueueJobVisualRole:
    """Return the visual queue role for one job."""

    if job.status in _ACTIVE_STATUSES:
        return "active"
    if job.status == "pending":
        return "pending"
    return "resolved"


def _queue_interaction_role(
    visual_role: QueueJobVisualRole,
) -> QueueJobInteractionRole:
    """Return the row interaction role from its visual role."""

    if visual_role == "pending":
        return "draggable"
    if visual_role == "resolved":
        return "context"
    return "none"


def _queue_subtitle(
    job: GenerationQueueJob,
    pending_ahead_by_job_id: dict[str, int],
) -> str:
    """Return compact status detail for one queue row."""

    if job.status == "pending":
        ahead_count = pending_ahead_by_job_id.get(job.job_id, 0)
        if ahead_count == 0:
            return "Next"
        return f"Waiting - {ahead_count} ahead"
    if job.status == "dispatching":
        return "Preparing"
    if job.status == "comfy_pending":
        return "Queued in Comfy"
    if job.status == "running":
        if job.progress_percent is None:
            return "Running"
        percent = int(max(0.0, min(100.0, job.progress_percent)) + 0.5)
        return f"{percent}% complete"
    if job.status == "completed":
        duration_text = format_generation_duration(job.execution_duration_ms)
        if duration_text:
            return f"Completed, {duration_text}"
        return "Completed"
    if job.status == "cancelled":
        if job.output_count == 0:
            return "Cancelled - No outputs saved"
        return f"Cancelled - {_output_count_text(job.output_count)} saved"
    if job.status == "failed":
        return f"Failed - {_queue_failure_summary(job)}"
    return _STATUS_LABELS.get(job.status, job.status)


def _queue_failure_summary(job: GenerationQueueJob) -> str:
    """Return a bounded failure summary for queue row subtitles."""

    summary = job.failure_summary or summarize_generation_failure(
        job.failure_message,
        detail=job.failure_detail,
    )
    normalized = " ".join(summary.strip().split())
    if not normalized:
        normalized = "Generation failed"
    return _right_elided_text(normalized, _MAX_FAILURE_SUBTITLE_SUMMARY_LENGTH)


def _right_elided_text(text: str, max_length: int) -> str:
    """Return text elided on the right to a character budget."""

    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return "." * max(0, max_length)
    return f"{text[: max_length - 3].rstrip()}..."


def _output_count_text(output_count: int) -> str:
    """Return pluralized output count text."""

    if output_count == 1:
        return "1 output"
    return f"{output_count} outputs"


def _queue_tooltip(job: GenerationQueueJob) -> str | None:
    """Return optional diagnostic tooltip content for one queue row."""

    details: list[str] = []
    if job.prompt_id is not None:
        details.append(f"Prompt: {job.prompt_id}")
    if job.status == "failed" and job.failure_summary is not None:
        _append_tooltip_detail(details, job.failure_summary)
    if job.failure_message is not None:
        _append_tooltip_detail(details, job.failure_message)
    if job.failure_detail is not None and job.failure_detail != job.failure_message:
        _append_tooltip_detail(details, job.failure_detail)
    if job.last_output_path is not None:
        _append_tooltip_detail(details, f"Last output: {job.last_output_path}")
    if not details:
        return None
    return "\n".join(details)


def _append_tooltip_detail(details: list[str], text: str) -> None:
    """Append one non-empty tooltip line without exact duplicates."""

    normalized = text.strip()
    if normalized and normalized not in details:
        details.append(normalized)


__all__ = [
    "QueueBucketDividerView",
    "QueueDisplayItem",
    "QueueJobInteractionRole",
    "QueueJobRowAction",
    "QueueJobRowView",
    "QueueJobVisualRole",
    "queue_display_item_rows",
    "queue_job_display_items",
    "queue_job_row_view",
    "queue_job_row_views",
    "should_show_pending_resolved_separator",
]
