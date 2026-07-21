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

"""Validate semantic identities before reusing projection line suffixes."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from .model import (
    PromptProjectionDocument,
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from .snapshot import (
    PromptProjectionFragment,
    PromptProjectionInlineObjectFragment,
    PromptProjectionLineSnapshot,
    PromptProjectionTextFragment,
)


@dataclass(frozen=True, slots=True)
class PromptReusedFragmentIdentity:
    """Carry semantic IDs rebound to a new projection document."""

    run_id: str
    token_id: str | None


class PromptReusedLineSemanticResolver:
    """Resolve shifted reused fragments against one new projection document."""

    def __init__(self, projection_document: PromptProjectionDocument) -> None:
        """Retain current semantics without eagerly walking the document."""

        self._projection_document = projection_document
        self._runs: tuple[PromptProjectionRun, ...] | None = None
        self._run_starts: tuple[int, ...] | None = None

    def identity_for(
        self,
        fragment: PromptProjectionFragment,
        *,
        projection_delta: int,
    ) -> PromptReusedFragmentIdentity | None:
        """Return the new run/token IDs when visible fragment content still matches."""

        run = self._run_for_projection_position(
            fragment.projection_start + projection_delta
        )
        if run is None or not _fragment_matches_run(
            fragment,
            run=run,
            projection_delta=projection_delta,
        ):
            return None
        if (
            run.token_id is not None
            and self._projection_document.token_by_id(run.token_id) is None
        ):
            return None
        return PromptReusedFragmentIdentity(
            run_id=run.run_id,
            token_id=run.token_id,
        )

    def _run_for_projection_position(
        self,
        projection_position: int,
    ) -> PromptProjectionRun | None:
        """Return the indexed run containing one shifted projection position."""

        optimized_lookup = getattr(
            self._projection_document.runs,
            "run_at_projection_position",
            None,
        )
        if callable(optimized_lookup):
            run = optimized_lookup(projection_position)
            return run if isinstance(run, PromptProjectionRun) else None
        runs = self._runs
        run_starts = self._run_starts
        if runs is None or run_starts is None:
            runs = tuple(self._projection_document.runs)
            run_starts = tuple(run.projection_start for run in runs)
            self._runs = runs
            self._run_starts = run_starts
        if not runs:
            return None
        run_index = bisect_right(run_starts, projection_position) - 1
        if run_index < 0:
            return None
        run = runs[run_index]
        if run.projection_start <= projection_position < run.projection_end:
            return run
        return None


def reusable_suffix_semantics_by_line(
    lines: Sequence[PromptProjectionLineSnapshot],
    resolver: PromptReusedLineSemanticResolver,
    *,
    projection_delta: int,
) -> tuple[bool, ...]:
    """Return whether every line after each index can rebind to new semantics."""

    safe_after = [True] * len(lines)
    downstream_safe = True
    for line_index in range(len(lines) - 1, -1, -1):
        safe_after[line_index] = downstream_safe
        downstream_safe = downstream_safe and _line_semantics_resolve(
            lines[line_index],
            resolver,
            projection_delta=projection_delta,
        )
    return tuple(safe_after)


def _line_semantics_resolve(
    line: PromptProjectionLineSnapshot,
    resolver: PromptReusedLineSemanticResolver,
    *,
    projection_delta: int,
) -> bool:
    """Return whether every reused fragment can bind to matching new semantics."""

    return all(
        resolver.identity_for(fragment, projection_delta=projection_delta) is not None
        for fragment in line.fragments
    )


def _fragment_matches_run(
    fragment: PromptProjectionFragment,
    *,
    run: PromptProjectionRun,
    projection_delta: int,
) -> bool:
    """Return whether one shifted fragment is an unchanged slice of a new run."""

    shifted_start = fragment.projection_start + projection_delta
    shifted_end = fragment.projection_end + projection_delta
    if shifted_end > run.projection_end:
        return False
    if isinstance(fragment, PromptProjectionTextFragment):
        if run.kind is not PromptProjectionRunKind.TEXT:
            return False
        local_start = shifted_start - run.projection_start
        local_end = shifted_end - run.projection_start
        return run.display_text[local_start:local_end] == fragment.text
    if isinstance(fragment, PromptProjectionInlineObjectFragment):
        return bool(
            run.kind is PromptProjectionRunKind.INLINE_OBJECT
            and run.renderer_key == fragment.renderer_key
            and shifted_start == run.projection_start
            and shifted_end == run.projection_end
        )
    return False


__all__ = [
    "PromptReusedFragmentIdentity",
    "PromptReusedLineSemanticResolver",
    "reusable_suffix_semantics_by_line",
]
