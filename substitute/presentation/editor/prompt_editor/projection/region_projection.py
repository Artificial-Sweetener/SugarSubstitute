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

"""Project canonical regional separators into non-content structural runs."""

from __future__ import annotations

from dataclasses import dataclass, replace

from substitute.application.prompt_editor import (
    PromptRegionSeparatorView,
    PromptRegionStructureView,
)
from substitute.domain.prompt.region_structure_parser import REGION_SEPARATOR_TOKEN

from .model import (
    PromptProjectionRun,
    PromptProjectionRunKind,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)


@dataclass(frozen=True, slots=True)
class PromptRegionProjection:
    """Return the structural run stream and separator tokens for one document."""

    runs: tuple[PromptProjectionRun, ...]
    tokens: tuple[PromptProjectionToken, ...]


class PromptRegionProjectionBuilder:
    """Replace exact separator source lines with non-inline structural rows."""

    def build(
        self,
        runs: tuple[PromptProjectionRun, ...],
        structure: PromptRegionStructureView,
    ) -> PromptRegionProjection:
        """Split plain runs around separators and emit one structural run per line."""

        separators = structure.separators
        if not separators:
            return PromptRegionProjection(runs=runs, tokens=())

        separator_index = 0
        projected_runs: list[PromptProjectionRun] = []
        tokens: list[PromptProjectionToken] = []
        for run in runs:
            if run.kind is not PromptProjectionRunKind.TEXT or run.token_id is not None:
                projected_runs.append(run)
                continue
            source_cursor = run.source_start
            while (
                separator_index < len(separators)
                and separators[separator_index].line_start < run.source_end
            ):
                separator = separators[separator_index]
                if separator.line_start < source_cursor:
                    raise ValueError(
                        "Regional separator overlaps projected source content."
                    )
                if separator.line_end > run.source_end:
                    break
                text_run = _slice_text_run(
                    run,
                    source_start=source_cursor,
                    source_end=separator.line_start,
                )
                if text_run is not None:
                    projected_runs.append(text_run)
                token = _separator_token(separator)
                tokens.append(token)
                projected_runs.append(_separator_run(separator, token))
                source_cursor = separator.line_end
                separator_index += 1
            trailing_run = _slice_text_run(
                run,
                source_start=source_cursor,
                source_end=run.source_end,
            )
            if trailing_run is not None:
                projected_runs.append(trailing_run)

        if separator_index != len(separators):
            raise ValueError(
                "Regional separator was not covered by a plain projection run."
            )
        return PromptRegionProjection(
            runs=_recompute_projection_ranges(tuple(projected_runs)),
            tokens=tuple(tokens),
        )


def _separator_token(separator: PromptRegionSeparatorView) -> PromptProjectionToken:
    """Build the atomic semantic token owning one structural separator."""

    return PromptProjectionToken(
        token_id=f"region-separator:{separator.token_start}:{separator.token_end}",
        kind=PromptProjectionTokenKind.REGION_SEPARATOR,
        source_start=separator.token_start,
        source_end=separator.token_end,
        display_text=REGION_SEPARATOR_TOKEN,
    )


def _separator_run(
    separator: PromptRegionSeparatorView,
    token: PromptProjectionToken,
) -> PromptProjectionRun:
    """Build one renderer-free structural row spanning its consumed source line."""

    return PromptProjectionRun(
        run_id=f"region-row:{separator.line_start}:{separator.line_end}",
        kind=PromptProjectionRunKind.STRUCTURAL_ROW,
        source_start=separator.line_start,
        source_end=separator.line_end,
        display_text="",
        source_positions=(separator.line_start, token.source_end, separator.line_end),
        projection_start=0,
        projection_end=1,
        token_id=token.token_id,
    )


def _slice_text_run(
    run: PromptProjectionRun,
    *,
    source_start: int,
    source_end: int,
) -> PromptProjectionRun | None:
    """Return one source-bounded slice of an existing plain text run."""

    if source_end <= source_start:
        return None
    try:
        local_start = run.source_positions.index(source_start)
        local_end = run.source_positions.index(source_end)
    except ValueError as error:
        raise ValueError(
            "Separator boundary is absent from its plain text run."
        ) from error
    return replace(
        run,
        run_id=f"region-text:{source_start}:{source_end}",
        source_start=source_start,
        source_end=source_end,
        display_text=run.display_text[local_start:local_end],
        source_positions=tuple(run.source_positions[local_start : local_end + 1]),
        projection_start=0,
        projection_end=local_end - local_start,
    )


def _recompute_projection_ranges(
    runs: tuple[PromptProjectionRun, ...],
) -> tuple[PromptProjectionRun, ...]:
    """Assign contiguous projection ranges after structural rows are inserted."""

    projection_position = 0
    projected_runs: list[PromptProjectionRun] = []
    for run in runs:
        run_length = len(run.display_text) if run.is_text else 1
        projected_runs.append(
            replace(
                run,
                projection_start=projection_position,
                projection_end=projection_position + run_length,
            )
        )
        projection_position += run_length
    return tuple(projected_runs)


__all__ = ["PromptRegionProjection", "PromptRegionProjectionBuilder"]
