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

from substitute.presentation.text_coordinates import TextCoordinateMap

from .model import (
    PromptProjectionCaretMap,
    PromptProjectionCaretPlacement,
    PromptProjectionCaretState,
    PromptProjectionCaretStop,
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionRunRole,
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptProjectionTokenNavigationMode,
)


def build_prompt_projection_caret_map(
    *,
    runs: tuple[PromptProjectionRun, ...],
    tokens: tuple[PromptProjectionToken, ...],
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
    stops: list[PromptProjectionCaretStop] = []
    tokens_with_leading_edge: set[str] = set()

    def append_stop(
        projection_position: int,
        state: PromptProjectionCaretState,
    ) -> None:
        stops.append(
            PromptProjectionCaretStop(
                visual_index=len(stops),
                projection_position=projection_position,
                state=state,
            )
        )

    def pop_plain_boundary_if_present(
        *,
        projection_position: int,
        source_position: int,
    ) -> None:
        if not stops:
            return
        last_stop = stops[-1]
        if (
            last_stop.projection_position == projection_position
            and last_stop.state.source_position == source_position
            and last_stop.state.placement is PromptProjectionCaretPlacement.PLAIN_TEXT
        ):
            stops.pop()

    def append_inline_preview_boundary_if_missing(
        run: PromptProjectionRun,
    ) -> None:
        """Expose one collapsed insertion stop before a ghost text run."""

        if not run.ghosted:
            return
        if stops:
            last_stop = stops[-1]
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
                stops.extend(
                    _plain_text_caret_stops_for_run(
                        run,
                        visual_index_start=len(stops),
                        boundary_start_index=0 if not stops else 1,
                    )
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
            stops.extend(
                _token_text_caret_stops_for_run(
                    run,
                    token=token,
                    visual_index_start=len(stops),
                )
            )
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

    if not stops:
        return _empty_caret_map(
            tokens=tokens,
            source_length=source_length,
            projection_length=projection_length,
        )

    return PromptProjectionCaretMap(
        stops=tuple(stops),
        tokens=tokens,
        source_length=source_length,
        projection_length=projection_length,
    )


def _empty_caret_map(
    *,
    tokens: tuple[PromptProjectionToken, ...],
    source_length: int,
    projection_length: int,
) -> PromptProjectionCaretMap:
    """Build the canonical caret map for an empty projection."""

    empty_state = PromptProjectionCaretState(source_position=0)
    return PromptProjectionCaretMap(
        stops=(PromptProjectionCaretStop(0, 0, empty_state),),
        tokens=tokens,
        source_length=source_length,
        projection_length=projection_length,
    )


def _single_plain_text_run(
    runs: tuple[PromptProjectionRun, ...],
    tokens: tuple[PromptProjectionToken, ...],
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


def _plain_text_caret_stops_for_run(
    run: PromptProjectionRun,
    *,
    visual_index_start: int,
    boundary_start_index: int,
) -> tuple[PromptProjectionCaretStop, ...]:
    """Return plain-text caret stops for one source-backed text run."""

    return tuple(
        PromptProjectionCaretStop(
            visual_index=visual_index_start + visual_offset,
            projection_position=run.projection_start + boundary_index,
            state=PromptProjectionCaretState(
                source_position=run.source_positions[boundary_index],
                placement=PromptProjectionCaretPlacement.PLAIN_TEXT,
                run_id=run.run_id,
            ),
        )
        for visual_offset, boundary_index in enumerate(
            boundary
            for boundary in TextCoordinateMap(run.display_text).grapheme_boundaries()
            if boundary >= boundary_start_index
        )
    )


def _token_text_caret_stops_for_run(
    run: PromptProjectionRun,
    *,
    token: PromptProjectionToken,
    visual_index_start: int,
) -> tuple[PromptProjectionCaretStop, ...]:
    """Return text-content caret stops for one token-owned text run."""

    return tuple(
        PromptProjectionCaretStop(
            visual_index=visual_index_start + token_slot,
            projection_position=run.projection_start + token_slot,
            state=PromptProjectionCaretState(
                source_position=source_position,
                placement=PromptProjectionCaretPlacement.TOKEN_CONTENT,
                token_id=token.token_id,
                run_id=run.run_id,
                token_slot=token_slot,
            ),
        )
        for token_slot in TextCoordinateMap(run.display_text).grapheme_boundaries()
        for source_position in (run.source_positions[token_slot],)
    )


def _single_plain_text_caret_map(
    run: PromptProjectionRun,
    *,
    tokens: tuple[PromptProjectionToken, ...],
    source_length: int,
    projection_length: int,
) -> PromptProjectionCaretMap:
    """Build a caret map for the common token-free single-run document shape."""

    return PromptProjectionCaretMap(
        stops=_plain_text_caret_stops_for_run(
            run,
            visual_index_start=0,
            boundary_start_index=0,
        ),
        tokens=tokens,
        source_length=source_length,
        projection_length=projection_length,
    )


__all__ = ["build_prompt_projection_caret_map"]
