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

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)
from .models import (
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
        self._resolved_runs: dict[
            tuple[str, int],
            tuple[PromptProjectionRun, PromptReusedFragmentIdentity] | None,
        ] = {}

    def identity_for(
        self,
        fragment: PromptProjectionFragment,
        *,
        projection_delta: int,
    ) -> PromptReusedFragmentIdentity | None:
        """Return the new run/token IDs when visible fragment content still matches."""

        preserves_identity = getattr(
            self._projection_document.runs,
            "preserves_run_identity",
            None,
        )
        if callable(preserves_identity) and bool(preserves_identity(fragment.run_id)):
            return PromptReusedFragmentIdentity(
                run_id=fragment.run_id,
                token_id=fragment.token_id,
            )
        cache_key = (fragment.run_id, projection_delta)
        if cache_key in self._resolved_runs:
            resolved = self._resolved_runs[cache_key]
            if resolved is None:
                return None
            cached_run, identity = resolved
            return (
                identity
                if _fragment_matches_run(
                    fragment,
                    run=cached_run,
                    projection_delta=projection_delta,
                )
                else None
            )
        run = self._run_for_projection_position(
            fragment.projection_start + projection_delta
        )
        if run is None or not _fragment_matches_run(
            fragment,
            run=run,
            projection_delta=projection_delta,
        ):
            self._resolved_runs[cache_key] = None
            return None
        if (
            run.token_id is not None
            and self._projection_document.token_by_id(run.token_id) is None
        ):
            self._resolved_runs[cache_key] = None
            return None
        identity = PromptReusedFragmentIdentity(
            run_id=run.run_id,
            token_id=run.token_id,
        )
        self._resolved_runs[cache_key] = (run, identity)
        return identity

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
        downstream_safe = downstream_safe and line_semantics_resolve(
            lines[line_index],
            resolver,
            projection_delta=projection_delta,
        )
    return tuple(safe_after)


def earliest_reusable_suffix_line_index(
    lines: Sequence[PromptProjectionLineSnapshot],
    reusable_semantics: Sequence[bool],
    *,
    first_line_index: int,
    edit_end: int,
) -> int | None:
    """Return the first downstream line whose remaining suffix can be rebound."""

    for line_index in range(first_line_index, len(lines)):
        if (
            lines[line_index].source_start >= edit_end
            and reusable_semantics[line_index]
        ):
            return line_index
    return None


def earliest_unresolvable_line_index(
    lines: Sequence[PromptProjectionLineSnapshot],
    resolver: PromptReusedLineSemanticResolver,
    *,
    stop_index: int,
) -> int | None:
    """Return the first prefix line that cannot bind to current semantics."""

    for line_index in range(min(stop_index, len(lines))):
        if not line_semantics_resolve(
            lines[line_index],
            resolver,
            projection_delta=0,
        ):
            return line_index
    return None


def line_semantics_resolve(
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


def line_semantic_identity_is_current(
    line: PromptProjectionLineSnapshot,
    resolver: PromptReusedLineSemanticResolver,
) -> bool:
    """Return whether every fragment already exposes its current semantic IDs."""

    for fragment in line.fragments:
        identity = resolver.identity_for(fragment, projection_delta=0)
        if identity is None or (
            identity.run_id != fragment.run_id or identity.token_id != fragment.token_id
        ):
            return False
    return True


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
    "earliest_reusable_suffix_line_index",
    "earliest_unresolvable_line_index",
    "line_semantic_identity_is_current",
    "line_semantics_resolve",
    "PromptReusedFragmentIdentity",
    "PromptReusedLineSemanticResolver",
    "reusable_suffix_semantics_by_line",
]
