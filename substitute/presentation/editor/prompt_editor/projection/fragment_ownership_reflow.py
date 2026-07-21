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

"""Widen canonical reflow edits to cover changed fragment-owner identities."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import zip_longest

from .model import PromptProjectionDocument, PromptProjectionRun


@dataclass(frozen=True, slots=True)
class PromptProjectionReflowEdit:
    """Carry one source edit whose bounds safely own canonical reflow."""

    start: int
    end: int
    replacement_text: str


def reflow_edit_including_fragment_identity_changes(
    previous_document: PromptProjectionDocument,
    projection_document: PromptProjectionDocument,
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> PromptProjectionReflowEdit:
    """Return an equivalent edit widened over earlier canonicalized run IDs.

    Optimistic plain edits retain stable run IDs for fast geometry reuse. A later
    canonical document can replace those IDs before the immediate source edit.
    Widening the equivalent edit keeps every preserved prefix fragment owned by
    the new document without changing the edit's source or projection delta.
    """

    identity_change_start = _earliest_identity_change_before(
        previous_document,
        projection_document,
        source_limit=start,
    )
    if identity_change_start is None:
        return PromptProjectionReflowEdit(start, end, replacement_text)
    replacement_end = start + len(replacement_text)
    return PromptProjectionReflowEdit(
        start=identity_change_start,
        end=end,
        replacement_text=projection_document.source_text[
            identity_change_start:replacement_end
        ],
    )


def _earliest_identity_change_before(
    previous_document: PromptProjectionDocument,
    projection_document: PromptProjectionDocument,
    *,
    source_limit: int,
) -> int | None:
    """Return the first changed run identity strictly before a reflow hint."""

    for previous_run, run in zip_longest(
        previous_document.runs,
        projection_document.runs,
    ):
        candidates = tuple(
            candidate for candidate in (previous_run, run) if candidate is not None
        )
        if not candidates or all(
            candidate.source_start >= source_limit for candidate in candidates
        ):
            return None
        if _fragment_owner_identity_matches(previous_run, run):
            continue
        return min(candidate.source_start for candidate in candidates)
    return None


def _fragment_owner_identity_matches(
    previous_run: PromptProjectionRun | None,
    run: PromptProjectionRun | None,
) -> bool:
    """Return whether two ordered runs expose the same fragment owner IDs."""

    return bool(
        previous_run is not None
        and run is not None
        and previous_run.run_id == run.run_id
        and previous_run.token_id == run.token_id
    )


__all__ = [
    "PromptProjectionReflowEdit",
    "reflow_edit_including_fragment_identity_changes",
]
