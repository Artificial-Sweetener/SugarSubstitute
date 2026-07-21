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

"""Build canonical caret maps from committed prompt projection runs."""

from __future__ import annotations

from collections.abc import Sequence

from .caret_stop_sequence import (
    PromptProjectionCaretStopSequence,
    PromptProjectionCaretStopSequenceBuilder,
)
from .model import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionRunRole,
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)


def build_prompt_projection_caret_map(
    *,
    runs: Sequence[PromptProjectionRun],
    tokens: Sequence[PromptProjectionToken],
    source_length: int,
    projection_length: int,
) -> PromptProjectionCaretMap:
    """Build the ordered caret-stop map from committed projection runs and tokens."""

    if not runs:
        return _empty_caret_map(
            tokens=tokens,
            source_length=source_length,
            projection_length=projection_length,
        )

    plain_text_run = _single_plain_text_run(runs, tokens)
    if plain_text_run is not None:
        return _single_plain_text_caret_map(
            plain_text_run,
            tokens=tokens,
            source_length=source_length,
            projection_length=projection_length,
        )

    tokens_by_id = {token.token_id: token for token in tokens}
    stop_builder = PromptProjectionCaretStopSequenceBuilder()
    tokens_with_leading_edge: set[str] = set()

    def append_stop(
        projection_position: int,
        state: PromptProjectionCaretState,
    ) -> None:
        stop_builder.append_state(projection_position, state)

    def pop_plain_boundary_if_present(
        *,
        projection_position: int,
        source_position: int,
    ) -> None:
        stop_builder.pop_plain_boundary_if_present(
            projection_position=projection_position,
            source_position=source_position,
        )

    def append_inline_preview_boundary_if_missing(
        run: PromptProjectionRun,
    ) -> None:
        """Expose one collapsed insertion stop before a ghost text run."""

        if not run.ghosted:
            return
        if stop_builder.has_stops:
            last_stop = stop_builder.last_stop
            assert last_stop is not None
            if (
                last_stop.projection_position == run.projection_start
                and last_stop.state.source_position == run.source_start
            ):
                return
        append_stop(
            run.projection_start,
            PromptProjectionCaretState(
                source_position=run.source_start,
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT
                if run.token_id is None
                else PromptProjectionCaretPlacement.TOKEN_CONTENT,
                token_id=run.token_id,
                run_id=run.run_id,
                token_slot=0 if run.token_id is not None else None,
            ),
        )

    for run in runs:
        if run.kind is PromptProjectionRunKind.TEXT:
            if not run.source_backed:
                append_inline_preview_boundary_if_missing(run)
                continue
            if run.token_id is None:
                stop_builder.append_plain_text_run(
                    run,
                    boundary_start_index=0 if not stop_builder.has_stops else 1,
                )
                continue

            token = tokens_by_id[run.token_id]
            if token.token_id not in tokens_with_leading_edge:
                pop_plain_boundary_if_present(
                    projection_position=run.projection_start,
                    source_position=token.source_start,
                )
                append_stop(
                    run.projection_start,
                    PromptProjectionCaretState(
                        source_position=token.source_start,
                        placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
                        token_id=token.token_id,
                        run_id=run.run_id,
                    ),
                )
                tokens_with_leading_edge.add(token.token_id)
            stop_builder.append_token_text_run(run, token=token)
            if token.kind is PromptProjectionTokenKind.SCENE:
                append_stop(
                    run.projection_end,
                    PromptProjectionCaretState(
                        source_position=token.source_end,
                        placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                        token_id=token.token_id,
                        run_id=run.run_id,
                    ),
                )
            continue

        assert run.token_id is not None
        token = tokens_by_id[run.token_id]
        if token.navigation_mode is PromptProjectionTokenNavigationMode.ATOMIC:
            pop_plain_boundary_if_present(
                projection_position=run.projection_start,
                source_position=token.source_start,
            )
            append_stop(
                run.projection_start,
                PromptProjectionCaretState(
                    source_position=token.source_start,
                    placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
                    token_id=token.token_id,
                    run_id=run.run_id,
                ),
            )
            tokens_with_leading_edge.add(token.token_id)
        elif run.role is PromptProjectionRunRole.TOKEN_LEADING_DECORATION:
            pop_plain_boundary_if_present(
                projection_position=run.projection_start,
                source_position=token.source_start,
            )
            if token.token_id not in tokens_with_leading_edge:
                append_stop(
                    run.projection_end,
                    PromptProjectionCaretState(
                        source_position=token.source_start,
                        placement=PromptProjectionCaretPlacement.TOKEN_LEADING_EDGE,
                        token_id=token.token_id,
                        run_id=run.run_id,
                    ),
                )
                tokens_with_leading_edge.add(token.token_id)
            continue
        append_stop(
            run.projection_end,
            PromptProjectionCaretState(
                source_position=token.source_end,
                placement=PromptProjectionCaretPlacement.TOKEN_TRAILING_EDGE,
                token_id=token.token_id,
                run_id=run.run_id,
            ),
        )

    if not stop_builder.has_stops:
        return _empty_caret_map(
            tokens=tokens,
            source_length=source_length,
            projection_length=projection_length,
        )

    return PromptProjectionCaretMap(
        stops=stop_builder.build(),
        tokens=tokens,
        source_length=source_length,
        projection_length=projection_length,
    )


def _empty_caret_map(
    *,
    tokens: Sequence[PromptProjectionToken],
    source_length: int,
    projection_length: int,
) -> PromptProjectionCaretMap:
    """Build the canonical caret map for an empty projection."""

    empty_state = PromptProjectionCaretState(source_position=0)
    return PromptProjectionCaretMap(
        stops=_single_explicit_stop_sequence(empty_state),
        tokens=tokens,
        source_length=source_length,
        projection_length=projection_length,
    )


def _single_plain_text_run(
    runs: Sequence[PromptProjectionRun],
    tokens: Sequence[PromptProjectionToken],
) -> PromptProjectionRun | None:
    """Return a source-backed single plain-text run when caret mapping is trivial."""

    if tokens or len(runs) != 1:
        return None
    run = runs[0]
    if run.kind is not PromptProjectionRunKind.TEXT:
        return None
    if run.token_id is not None or not run.source_backed:
        return None
    return run


def _single_plain_text_caret_map(
    run: PromptProjectionRun,
    *,
    tokens: Sequence[PromptProjectionToken],
    source_length: int,
    projection_length: int,
) -> PromptProjectionCaretMap:
    """Build a caret map for the common token-free single-run document shape."""

    return PromptProjectionCaretMap(
        stops=_plain_text_stop_sequence(run),
        tokens=tokens,
        source_length=source_length,
        projection_length=projection_length,
    )


def _plain_text_stop_sequence(
    run: PromptProjectionRun,
) -> PromptProjectionCaretStopSequence:
    """Return a compact canonical sequence for one plain-text run."""

    builder = PromptProjectionCaretStopSequenceBuilder()
    builder.append_plain_text_run(run, boundary_start_index=0)
    return builder.build()


def _single_explicit_stop_sequence(
    state: PromptProjectionCaretState,
) -> PromptProjectionCaretStopSequence:
    """Return a compact canonical sequence containing one explicit stop."""

    builder = PromptProjectionCaretStopSequenceBuilder()
    builder.append_state(0, state)
    return builder.build()


__all__ = ["build_prompt_projection_caret_map"]
