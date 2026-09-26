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

"""Resolve and cancel projection-owned completion records exactly once."""

from __future__ import annotations

from collections.abc import Sequence

from substitute.shared.logging.logger import get_logger, log_debug

from .projection_session_models import (
    PendingInsertCompletion,
    PendingProjectionCompletion,
)

_LOGGER = get_logger("presentation.editor.panel.projection_completion_resolution")


def resolve_insert_completions(
    completions: Sequence[PendingInsertCompletion],
    *,
    reason: str,
) -> None:
    """Invoke claimed insert callbacks after replacement projection succeeds."""

    for completion in completions:
        if completion.resolved:
            continue
        completion.resolved = True
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_resolved",
            workflow_id=completion.workflow_id,
            cube_alias=completion.cube_alias,
            reason=reason,
            superseded_reason=completion.superseded_reason or "",
            completion_phase=completion.completion_phase,
        )
        if completion.on_complete is not None:
            completion.on_complete()


def resolve_projection_completions(
    completions: Sequence[PendingProjectionCompletion],
    *,
    reason: str,
) -> None:
    """Invoke full-projection callbacks after replacement projection succeeds."""

    for completion in completions:
        if completion.resolved:
            continue
        completion.resolved = True
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="projection_completion_resolved",
            workflow_id=completion.workflow_id,
            reason=reason,
            superseded_reason=completion.superseded_reason or "",
            completion_reason=completion.reason,
            projection_alias_count=len(completion.aliases),
        )
        completion.on_complete()


def cancel_insert_completions(
    completions: Sequence[PendingInsertCompletion],
    *,
    reason: str,
) -> None:
    """Close insert callbacks without reporting successful readiness."""

    for completion in completions:
        if completion.resolved:
            continue
        completion.resolved = True
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="pending_insert_completion_cancelled",
            workflow_id=completion.workflow_id,
            cube_alias=completion.cube_alias,
            reason=reason,
            superseded_reason=completion.superseded_reason or "",
            completion_phase=completion.completion_phase,
        )


def cancel_projection_completions(
    completions: Sequence[PendingProjectionCompletion],
    *,
    reason: str,
) -> None:
    """Close projection callbacks without reporting successful readiness."""

    for completion in completions:
        if completion.resolved:
            continue
        completion.resolved = True
        log_debug(
            _LOGGER,
            "Cube load detail",
            event="projection_completion_cancelled",
            workflow_id=completion.workflow_id,
            reason=reason,
            superseded_reason=completion.superseded_reason or "",
            completion_reason=completion.reason,
            projection_alias_count=len(completion.aliases),
        )
