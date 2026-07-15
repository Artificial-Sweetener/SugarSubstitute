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

"""Open generation result snapshots as workspace tabs."""

from __future__ import annotations

from typing import Protocol

from substitute.application.generation import GenerationJobSnapshot
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("presentation.shell.generation_result_workspace_opener")


class GenerationResultFileActionsProtocol(Protocol):
    """Describe legacy Sugar snapshot opening owned by file actions."""

    def open_sugar_snapshot_as_new_workflow(
        self,
        *,
        workflow_name: str,
        sugar_script_text: str,
    ) -> None:
        """Open Sugar script text as a new workflow tab."""


def open_generation_job_as_workflow_for_view(
    *,
    generation_view: object,
    file_actions: GenerationResultFileActionsProtocol,
    job_id: str,
) -> None:
    """Open a visible generation job snapshot as a new workflow tab."""

    if _open_live_generation_result_workspace(
        generation_view=generation_view,
        job_id=job_id,
    ):
        return

    legacy_snapshot = legacy_generation_snapshot_for_job(
        generation_view=generation_view,
        job_id=job_id,
    )
    if legacy_snapshot is None:
        log_info(
            _LOGGER,
            "Generation job workspace open skipped; no snapshot available",
            job_id=job_id,
            operation="open_generation_job_as_workflow",
        )
        return
    file_actions.open_sugar_snapshot_as_new_workflow(
        workflow_name=legacy_snapshot.workflow_name,
        sugar_script_text=legacy_snapshot.sugar_script_text,
    )


def legacy_generation_snapshot_for_job(
    *,
    generation_view: object,
    job_id: str,
) -> GenerationJobSnapshot | None:
    """Return in-memory Sugar snapshot fallback for older queue surfaces."""

    queue_service = getattr(generation_view, "generation_job_queue_service", None)
    snapshot_for_job = getattr(queue_service, "snapshot_for_job", None)
    if not callable(snapshot_for_job):
        return None
    snapshot = snapshot_for_job(job_id)
    if isinstance(snapshot, GenerationJobSnapshot):
        return snapshot
    return None


def _open_live_generation_result_workspace(
    *,
    generation_view: object,
    job_id: str,
) -> bool:
    """Open a current-session generation result workspace when available."""

    result_snapshot_service = getattr(
        generation_view,
        "generation_result_snapshot_service",
        None,
    )
    build_for_live_job = getattr(result_snapshot_service, "build_for_live_job", None)
    materializer = getattr(
        generation_view,
        "generation_result_workspace_materializer",
        None,
    )
    materialize_result = getattr(
        materializer,
        "materialize_generation_result_workspace",
        None,
    )
    if not callable(build_for_live_job) or not callable(materialize_result):
        return False

    result = build_for_live_job(job_id)
    snapshot = getattr(result, "snapshot", None)
    if snapshot is None:
        return False

    warnings = materialize_result(snapshot.workspace)
    for warning in warnings:
        log_warning(
            _LOGGER,
            "Opened generation job with restore warning",
            job_id=job_id,
            repair=warning,
            operation="open_generation_job_as_workflow",
        )
    return True


__all__ = [
    "GenerationResultFileActionsProtocol",
    "legacy_generation_snapshot_for_job",
    "open_generation_job_as_workflow_for_view",
]
