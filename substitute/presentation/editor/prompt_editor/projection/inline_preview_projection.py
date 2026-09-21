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

"""Insert non-source-backed autocomplete previews into projection runs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from hashlib import blake2s

from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionInlinePreview,
)
from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
    PromptProjectionRunKind,
)


@dataclass(frozen=True, slots=True)
class _InlinePreviewInsertion:
    """Identify one source-backed run boundary that owns an insertion."""

    run_index: int
    local_boundary_index: int


class PromptInlinePreviewProjector:
    """Apply one transient preview without changing source ownership."""

    def project(
        self,
        runs: tuple[PromptProjectionRun, ...],
        *,
        source_length: int,
        preview: PromptProjectionInlinePreview | None,
    ) -> tuple[PromptProjectionRun, ...]:
        """Return runs with a valid preview inserted at its source boundary."""

        if preview is None or not preview.suffix_text:
            return runs
        if preview.source_position < 0 or preview.source_position > source_length:
            return runs
        insertion = _inline_preview_insertion(
            runs,
            source_position=preview.source_position,
        )
        if insertion is None:
            return runs
        insertion_run = runs[insertion.run_index]
        local_index = insertion.local_boundary_index
        next_runs = [*runs[: insertion.run_index]]
        next_runs.extend(_split_left_run(insertion_run, local_index))
        next_runs.append(
            _inline_preview_run(
                source_position=preview.source_position,
                suffix_text=preview.suffix_text,
                insertion_run=insertion_run,
            )
        )
        next_runs.extend(_split_right_run(insertion_run, local_index))
        next_runs.extend(runs[insertion.run_index + 1 :])
        return _runs_with_recomputed_projection_ranges(tuple(next_runs))


def _inline_preview_insertion(
    runs: tuple[PromptProjectionRun, ...],
    *,
    source_position: int,
) -> _InlinePreviewInsertion | None:
    """Return the source-backed text boundary that owns an insertion."""

    fallback: _InlinePreviewInsertion | None = None
    for run_index, run in enumerate(runs):
        if run.kind is not PromptProjectionRunKind.TEXT or not run.source_backed:
            continue
        try:
            local_boundary_index = _source_boundary_index(
                run.source_positions,
                source_position,
            )
        except ValueError:
            continue
        insertion = _InlinePreviewInsertion(run_index, local_boundary_index)
        if local_boundary_index > 0:
            return insertion
        if fallback is None:
            fallback = insertion
    return fallback


def _source_boundary_index(
    source_positions: Sequence[int],
    source_position: int,
) -> int:
    """Return the first local boundary matching one source position."""

    for index, candidate_position in enumerate(source_positions):
        if candidate_position == source_position:
            return index
    raise ValueError(source_position)


def _split_left_run(
    run: PromptProjectionRun,
    local_index: int,
) -> tuple[PromptProjectionRun, ...]:
    """Return the left source-backed split when it has visible text."""

    if local_index <= 0:
        return ()
    return (
        replace(
            run,
            run_id=f"{run.run_id}:preview-left",
            source_start=run.source_positions[0],
            source_end=run.source_positions[local_index],
            display_text=run.display_text[:local_index],
            source_positions=tuple(run.source_positions[: local_index + 1]),
            projection_start=0,
            projection_end=local_index,
        ),
    )


def _split_right_run(
    run: PromptProjectionRun,
    local_index: int,
) -> tuple[PromptProjectionRun, ...]:
    """Return the right source-backed split when it has visible text."""

    if local_index >= len(run.display_text):
        return ()
    display_text = run.display_text[local_index:]
    return (
        replace(
            run,
            run_id=f"{run.run_id}:preview-right",
            source_start=run.source_positions[local_index],
            source_end=run.source_positions[-1],
            display_text=display_text,
            source_positions=tuple(run.source_positions[local_index:]),
            projection_start=0,
            projection_end=len(display_text),
        ),
    )


def _inline_preview_run(
    *,
    source_position: int,
    suffix_text: str,
    insertion_run: PromptProjectionRun,
) -> PromptProjectionRun:
    """Return one visible ghost run that does not contribute source text."""

    suffix_hash = blake2s(suffix_text.encode("utf-8"), digest_size=4).hexdigest()
    return PromptProjectionRun(
        run_id=f"inline-preview:{source_position}:{suffix_hash}",
        kind=PromptProjectionRunKind.TEXT,
        source_start=source_position,
        source_end=source_position,
        display_text=suffix_text,
        source_positions=tuple(source_position for _ in range(len(suffix_text) + 1)),
        projection_start=0,
        projection_end=len(suffix_text),
        token_id=insertion_run.token_id,
        active=insertion_run.active,
        source_backed=False,
        ghosted=True,
        text_style_variant=insertion_run.text_style_variant,
    )


def _runs_with_recomputed_projection_ranges(
    runs: tuple[PromptProjectionRun, ...],
) -> tuple[PromptProjectionRun, ...]:
    """Return runs with contiguous projection ranges matching visible length."""

    next_runs: list[PromptProjectionRun] = []
    projection_position = 0
    for run in runs:
        run_length = len(run.display_text) if run.is_text else 1
        next_runs.append(
            replace(
                run,
                projection_start=projection_position,
                projection_end=projection_position + run_length,
            )
        )
        projection_position += run_length
    return tuple(next_runs)


__all__ = ["PromptInlinePreviewProjector"]
