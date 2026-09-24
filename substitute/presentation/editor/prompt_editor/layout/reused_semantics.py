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
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
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


@dataclass(frozen=True, slots=True)
class _ResolvedRun:
    """Cache one positional run match and whether its full semantics survived."""

    run: PromptProjectionRun
    identity: PromptReusedFragmentIdentity
    fully_reusable: bool


class PromptReusedLineSemanticResolver:
    """Resolve shifted reused fragments against one new projection document."""

    def __init__(self, projection_document: PromptProjectionDocument) -> None:
        """Retain current semantics without eagerly walking the document."""

        self._projection_document = projection_document
        self._previous_document: PromptProjectionDocument | None = None
        self._runs: tuple[PromptProjectionRun, ...] | None = None
        self._run_starts: tuple[int, ...] | None = None
        self._resolved_runs: dict[
            tuple[str, int, int],
            _ResolvedRun | None,
        ] = {}
        self._resolved_token_semantics: dict[tuple[str, str, int], bool] = {}

    @classmethod
    def after_source_edit(
        cls,
        projection_document: PromptProjectionDocument,
        *,
        previous_document: PromptProjectionDocument,
    ) -> PromptReusedLineSemanticResolver:
        """Return a resolver that validates each unchanged semantic run once."""

        resolver = cls(projection_document)
        resolver._previous_document = previous_document
        return resolver

    def identity_for(
        self,
        fragment: PromptProjectionFragment,
        *,
        projection_delta: int,
        source_delta: int = 0,
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
        cache_key = (fragment.run_id, source_delta, projection_delta)
        if cache_key in self._resolved_runs:
            resolved = self._resolved_runs[cache_key]
            if resolved is None:
                return None
            if resolved.fully_reusable:
                return resolved.identity
            return (
                resolved.identity
                if _fragment_matches_run(
                    fragment,
                    run=resolved.run,
                    projection_delta=projection_delta,
                )
                else None
            )
        previous_run = (
            None
            if self._previous_document is None
            else self._previous_document.run_by_id(fragment.run_id)
        )
        run = self._run_for_projection_position(
            fragment.projection_start + projection_delta
        )
        if previous_run is not None:
            if run is None:
                self._resolved_runs[cache_key] = None
                return None
            identity = PromptReusedFragmentIdentity(
                run_id=run.run_id,
                token_id=run.token_id,
            )
            fully_reusable = self._runs_match_after_source_edit(
                previous_run,
                run,
            )
            self._resolved_runs[cache_key] = _ResolvedRun(
                run=run,
                identity=identity,
                fully_reusable=fully_reusable,
            )
            if fully_reusable or _fragment_matches_run(
                fragment,
                run=run,
                projection_delta=projection_delta,
            ):
                return identity
            return None
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
        self._resolved_runs[cache_key] = _ResolvedRun(
            run=run,
            identity=identity,
            fully_reusable=False,
        )
        return identity

    def reusable_prefix_source_end(self) -> int:
        """Return the old source boundary through which complete runs still match."""

        previous_document = self._previous_document
        if previous_document is None:
            return 0
        source_end = 0
        for previous_run, current_run in zip(
            previous_document.runs,
            self._projection_document.runs,
            strict=False,
        ):
            if not self._runs_match_after_source_edit(
                previous_run,
                current_run,
                required_source_delta=0,
                required_projection_delta=0,
            ):
                break
            source_end = previous_run.source_end
        return source_end

    def reusable_suffix_source_start(
        self,
        *,
        source_delta: int,
        projection_delta: int,
    ) -> int:
        """Return the earliest old source boundary in the matching run suffix."""

        previous_document = self._previous_document
        if previous_document is None:
            return len(self._projection_document.source_text)
        source_start = len(previous_document.source_text)
        for previous_run, current_run in zip(
            reversed(previous_document.runs),
            reversed(self._projection_document.runs),
            strict=False,
        ):
            if not self._runs_match_after_source_edit(
                previous_run,
                current_run,
                required_source_delta=source_delta,
                required_projection_delta=projection_delta,
            ):
                break
            source_start = previous_run.source_start
        return source_start

    def line_identities_are_current(
        self,
        line: PromptProjectionLineSnapshot,
    ) -> bool:
        """Return whether one reused line already names current runs and tokens."""

        run_ids = self._projection_document.run_ids()
        token_ids = self._projection_document.token_ids()
        return all(
            fragment.run_id in run_ids
            and (fragment.token_id is None or fragment.token_id in token_ids)
            for fragment in line.fragments
        )

    def _runs_match_after_source_edit(
        self,
        previous_run: PromptProjectionRun,
        current_run: PromptProjectionRun,
        *,
        required_source_delta: int | None = None,
        required_projection_delta: int | None = None,
    ) -> bool:
        """Return whether one full run and its token retain shifted semantics."""

        source_delta = current_run.source_start - previous_run.source_start
        projection_delta = current_run.projection_start - previous_run.projection_start
        if (
            required_source_delta is not None and source_delta != required_source_delta
        ) or (
            required_projection_delta is not None
            and projection_delta != required_projection_delta
        ):
            return False
        if not _runs_have_shifted_semantics(
            previous_run,
            current_run,
            source_delta=source_delta,
            projection_delta=projection_delta,
        ):
            return False
        if previous_run.token_id is None:
            return current_run.token_id is None
        if current_run.token_id is None:
            return False
        token_cache_key = (
            previous_run.token_id,
            current_run.token_id,
            source_delta,
        )
        cached_token_match = self._resolved_token_semantics.get(token_cache_key)
        if cached_token_match is not None:
            return cached_token_match
        previous_document = self._previous_document
        assert previous_document is not None
        previous_token = previous_document.token_by_id(previous_run.token_id)
        current_token = self._projection_document.token_by_id(current_run.token_id)
        if previous_token is None or current_token is None:
            return False
        token_matches = _tokens_have_shifted_semantics(
            previous_token,
            current_token,
            source_delta=source_delta,
        )
        self._resolved_token_semantics[token_cache_key] = token_matches
        return token_matches

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
    source_delta: int,
    projection_delta: int,
    first_candidate_line_index: int = 0,
) -> tuple[bool, ...]:
    """Return suffix safety only where a line can participate in convergence."""

    first_candidate = max(0, min(first_candidate_line_index, len(lines)))
    reusable_source_start = resolver.reusable_suffix_source_start(
        source_delta=source_delta,
        projection_delta=projection_delta,
    )
    safe_after = [False] * len(lines)
    downstream_safe = True
    for line_index in range(len(lines) - 1, first_candidate - 1, -1):
        safe_after[line_index] = downstream_safe
        if lines[line_index].source_start >= reusable_source_start:
            continue
        downstream_safe = downstream_safe and line_semantics_resolve(
            lines[line_index],
            resolver,
            source_delta=source_delta,
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

    reusable_source_end = resolver.reusable_prefix_source_end()
    for line_index in range(min(stop_index, len(lines))):
        if lines[line_index].source_end <= reusable_source_end:
            continue
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
    source_delta: int = 0,
    projection_delta: int,
) -> bool:
    """Return whether every reused fragment can bind to matching new semantics."""

    return all(
        resolver.identity_for(
            fragment,
            source_delta=source_delta,
            projection_delta=projection_delta,
        )
        is not None
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


def _shift_optional(position: int | None, delta: int) -> int | None:
    """Return one optional source coordinate shifted by a constant."""

    return None if position is None else position + delta


def _runs_have_shifted_semantics(
    previous: PromptProjectionRun,
    current: PromptProjectionRun,
    *,
    source_delta: int,
    projection_delta: int,
) -> bool:
    """Return whether run geometry and presentation differ only by position."""

    return bool(
        current.kind is previous.kind
        and current.source_start == previous.source_start + source_delta
        and current.source_end == previous.source_end + source_delta
        and current.display_text == previous.display_text
        and _source_positions_are_shifted(
            previous.source_positions,
            current.source_positions,
            delta=source_delta,
        )
        and current.projection_start == previous.projection_start + projection_delta
        and current.projection_end == previous.projection_end + projection_delta
        and (current.token_id is None) == (previous.token_id is None)
        and current.renderer_key == previous.renderer_key
        and current.role is previous.role
        and current.active is previous.active
        and current.source_backed is previous.source_backed
        and current.ghosted is previous.ghosted
        and current.text_style_variant == previous.text_style_variant
    )


def _source_positions_are_shifted(
    previous: Sequence[int],
    current: Sequence[int],
    *,
    delta: int,
) -> bool:
    """Return whether every source boundary moved by one constant delta."""

    if len(previous) != len(current):
        return False
    if isinstance(previous, range) and isinstance(current, range):
        return current == range(
            previous.start + delta,
            previous.stop + delta,
            previous.step,
        )
    if len(previous) == 2:
        return bool(
            current[0] == previous[0] + delta and current[1] == previous[1] + delta
        )
    if len(previous) == 3:
        return bool(
            current[0] == previous[0] + delta
            and current[1] == previous[1] + delta
            and current[2] == previous[2] + delta
        )
    return all(
        current_position == previous_position + delta
        for previous_position, current_position in zip(previous, current, strict=True)
    )


def _tokens_have_shifted_semantics(
    previous: PromptProjectionToken,
    current: PromptProjectionToken,
    *,
    source_delta: int,
) -> bool:
    """Return whether token meaning and presentation survive a source shift."""

    return bool(
        current.kind is previous.kind
        and current.source_start == previous.source_start + source_delta
        and current.source_end == previous.source_end + source_delta
        and current.display_text == previous.display_text
        and current.value_text == previous.value_text
        and current.status_text == previous.status_text
        and current.style_variant == previous.style_variant
        and current.wildcard_display_tag == previous.wildcard_display_tag
        and current.wildcard_tag_is_explicit is previous.wildcard_tag_is_explicit
        and current.wildcard_tag_is_numeric is previous.wildcard_tag_is_numeric
        and current.wildcard_can_step_tag is previous.wildcard_can_step_tag
        and current.detail_text == previous.detail_text
        and current.lora_status is previous.lora_status
        and current.lora_status_reason == previous.lora_status_reason
        and current.lora_match_source == previous.lora_match_source
        and current.lora_authority is previous.lora_authority
        and current.lora_backend_value == previous.lora_backend_value
        and current.lora_version_text == previous.lora_version_text
        and current.lora_trained_words == previous.lora_trained_words
        and current.model_page_url == previous.model_page_url
        and current.thumbnail_variants == previous.thumbnail_variants
        and current.exists is previous.exists
        and current.active is previous.active
        and current.decoration_accented is previous.decoration_accented
        and current.synthetic is previous.synthetic
        and current.content_start
        == _shift_optional(previous.content_start, source_delta)
        and current.content_end == _shift_optional(previous.content_end, source_delta)
        and current.editing_value_text == previous.editing_value_text
        and current.editing_slot_width == previous.editing_slot_width
        and current.editing_caret_index == previous.editing_caret_index
        and current.editing_select_all is previous.editing_select_all
        and current.navigation_mode is previous.navigation_mode
    )


__all__ = [
    "earliest_reusable_suffix_line_index",
    "earliest_unresolvable_line_index",
    "line_semantics_resolve",
    "PromptReusedFragmentIdentity",
    "PromptReusedLineSemanticResolver",
    "reusable_suffix_semantics_by_line",
]
