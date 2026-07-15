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

"""Share typed workflow-surface projection and reconciliation results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.presentation.shell.workflow_surface_invalidation import (
    WorkflowSurface,
)


class SurfaceRefreshStatus(StrEnum):
    """Classify the outcome of one workflow-surface refresh operation."""

    SUCCESS = "success"
    SKIPPED_CLEAN = "skipped_clean"
    SKIPPED_STALE = "skipped_stale"
    SKIPPED_MISSING = "skipped_missing"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SurfaceRefreshResult:
    """Describe whether one surface operation may clean invalidation state."""

    workflow_id: str
    surface: WorkflowSurface
    status: SurfaceRefreshStatus
    cleanable: bool
    error: str
    elapsed_ms: float
    operation: str


@dataclass(frozen=True, slots=True)
class WorkflowUiPair:
    """Return workflow-scoped shell widgets materialized for a route."""

    cube_stack: object | None
    editor_panel: object | None
    created: bool


@dataclass(frozen=True, slots=True)
class ReconciliationToken:
    """Identify deferred reconciliation work for stale-callback detection."""

    workflow_id: str
    generation: int


def surface_result(
    *,
    workflow_id: str,
    surface: WorkflowSurface,
    status: SurfaceRefreshStatus,
    operation: str,
    elapsed_ms: float,
    cleanable: bool | None = None,
    error: str = "",
) -> SurfaceRefreshResult:
    """Build a result with conservative default cleanability."""

    if cleanable is None:
        cleanable = status in {
            SurfaceRefreshStatus.SUCCESS,
            SurfaceRefreshStatus.SKIPPED_CLEAN,
        }
    return SurfaceRefreshResult(
        workflow_id=workflow_id,
        surface=surface,
        status=status,
        cleanable=cleanable,
        error=error,
        elapsed_ms=elapsed_ms,
        operation=operation,
    )


__all__ = [
    "ReconciliationToken",
    "SurfaceRefreshResult",
    "SurfaceRefreshStatus",
    "WorkflowUiPair",
    "surface_result",
]
