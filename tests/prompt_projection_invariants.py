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

"""Validate prompt projection document invariants for tests."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionCaretPlacement,
    PromptProjectionDocument,
    PromptProjectionRun,
    PromptProjectionRunKind,
)


def validate_prompt_projection_document(document: PromptProjectionDocument) -> None:
    """Raise `ValueError` when committed projection fields disagree."""

    if document.mapping.source_length != len(document.source_text):
        raise ValueError(
            "Projection mapping source length does not match document source text."
        )
    if document.mapping.projection_length != len(document.projection_text):
        raise ValueError(
            "Projection mapping projection length does not match projection text."
        )
    _validate_run_source_positions(document)
    _validate_caret_stop_bounds(document)
    _validate_plain_text_caret_stops(document)


def _validate_run_source_positions(document: PromptProjectionDocument) -> None:
    """Validate source boundary counts and bounds for each projection run."""

    source_length = len(document.source_text)
    for run in document.runs:
        if run.kind is PromptProjectionRunKind.TEXT:
            expected_boundary_count = len(run.display_text) + 1
            if len(run.source_positions) != expected_boundary_count:
                raise ValueError(
                    f"Text run {run.run_id!r} has {len(run.source_positions)} "
                    f"source boundaries for {len(run.display_text)} visible chars."
                )
        for source_position in run.source_positions:
            if source_position < 0 or source_position > source_length:
                raise ValueError(
                    f"Run {run.run_id!r} source position {source_position} is "
                    f"outside document source length {source_length}."
                )


def _validate_caret_stop_bounds(document: PromptProjectionDocument) -> None:
    """Validate source and projection bounds for committed caret stops."""

    source_length = len(document.source_text)
    projection_length = len(document.projection_text)
    for stop in document.caret_map.stops:
        if stop.state.source_position < 0 or stop.state.source_position > source_length:
            raise ValueError(
                f"Caret stop source position {stop.state.source_position} is "
                f"outside document source length {source_length}."
            )
        if stop.projection_position < 0 or stop.projection_position > projection_length:
            raise ValueError(
                f"Caret stop projection position {stop.projection_position} is "
                f"outside projection length {projection_length}."
            )


def _validate_plain_text_caret_stops(document: PromptProjectionDocument) -> None:
    """Validate source-backed plain-text run boundaries against the caret map."""

    plain_runs = tuple(_source_backed_plain_text_runs(document))
    if len(plain_runs) == 1 and not document.tokens:
        caret_source_positions = tuple(
            stop.state.source_position for stop in document.caret_map.stops
        )
        run_source_positions = tuple(plain_runs[0].source_positions)
        if caret_source_positions != run_source_positions:
            raise ValueError(
                "Single plain-text projection caret stops do not match run "
                "source positions."
            )

    for run in plain_runs:
        run_stop_positions = tuple(
            stop.state.source_position
            for stop in document.caret_map.stops
            if stop.state.run_id == run.run_id
            and stop.state.placement is PromptProjectionCaretPlacement.PLAIN_TEXT
        )
        if run_stop_positions != tuple(sorted(run_stop_positions)):
            raise ValueError(
                f"Plain-text caret stops for run {run.run_id!r} are not monotonic."
            )
        missing_positions = tuple(
            source_position
            for source_position in run.source_positions
            if source_position not in run_stop_positions
        )
        if missing_positions:
            raise ValueError(
                f"Plain-text run {run.run_id!r} has source boundaries missing "
                f"from the caret map: {missing_positions!r}."
            )


def _source_backed_plain_text_runs(
    document: PromptProjectionDocument,
) -> tuple[PromptProjectionRun, ...]:
    """Return source-backed text runs that are not owned by semantic tokens."""

    return tuple(
        run
        for run in document.runs
        if run.kind is PromptProjectionRunKind.TEXT
        and run.source_backed
        and run.token_id is None
    )


__all__ = ["validate_prompt_projection_document"]
