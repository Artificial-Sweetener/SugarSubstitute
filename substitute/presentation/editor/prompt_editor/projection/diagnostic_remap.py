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

"""Remap prepared diagnostics across local prompt source edits."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticPayload,
    PromptDuplicateSegmentDiagnosticPayload,
)


def remap_diagnostics_after_source_edit(
    diagnostics: tuple[PromptDiagnostic, ...],
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> tuple[PromptDiagnostic, ...]:
    """Return diagnostics shifted across one source edit, dropping stale overlaps."""

    if not diagnostics:
        return diagnostics
    delta = len(replacement_text) - (end - start)
    return tuple(
        remapped_diagnostic
        for diagnostic in diagnostics
        if (
            remapped_diagnostic := _remap_diagnostic_after_source_edit(
                diagnostic,
                start=start,
                end=end,
                delta=delta,
            )
        )
        is not None
    )


def _remap_diagnostic_after_source_edit(
    diagnostic: PromptDiagnostic,
    *,
    start: int,
    end: int,
    delta: int,
) -> PromptDiagnostic | None:
    """Return a diagnostic shifted across a local edit, dropping stale overlaps."""

    if _ranges_overlap(diagnostic.source_start, diagnostic.source_end, start, end):
        return None
    if start == end and diagnostic.source_start <= start < diagnostic.source_end:
        return None
    return replace(
        diagnostic,
        source_start=_remap_position_after_source_edit_for_diagnostic(
            diagnostic.source_start,
            start=start,
            end=end,
            delta=delta,
        ),
        source_end=_remap_position_after_source_edit_for_diagnostic(
            diagnostic.source_end,
            start=start,
            end=end,
            delta=delta,
        ),
        payload=_remap_diagnostic_payload_after_source_edit(
            diagnostic.payload,
            start=start,
            end=end,
            delta=delta,
        ),
    )


def _remap_diagnostic_payload_after_source_edit(
    payload: PromptDiagnosticPayload,
    *,
    start: int,
    end: int,
    delta: int,
) -> PromptDiagnosticPayload:
    """Return diagnostic payload ranges shifted across a local edit."""

    if isinstance(payload, PromptDuplicateSegmentDiagnosticPayload):
        return replace(
            payload,
            first_source_start=_remap_position_after_source_edit_for_diagnostic(
                payload.first_source_start,
                start=start,
                end=end,
                delta=delta,
            ),
            first_source_end=_remap_position_after_source_edit_for_diagnostic(
                payload.first_source_end,
                start=start,
                end=end,
                delta=delta,
            ),
            duplicate_source_start=_remap_position_after_source_edit_for_diagnostic(
                payload.duplicate_source_start,
                start=start,
                end=end,
                delta=delta,
            ),
            duplicate_source_end=_remap_position_after_source_edit_for_diagnostic(
                payload.duplicate_source_end,
                start=start,
                end=end,
                delta=delta,
            ),
        )
    return payload


def _remap_position_after_source_edit_for_diagnostic(
    position: int,
    *,
    start: int,
    end: int,
    delta: int,
) -> int:
    """Return a diagnostic source position shifted across a non-overlapping edit."""

    if start == end:
        return position + delta if position >= start else position
    if position >= end:
        return position + delta
    if position > start:
        return start
    return position


def _ranges_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    """Return whether two half-open source ranges overlap."""

    return first_start < second_end and second_start < first_end


__all__ = ["remap_diagnostics_after_source_edit"]
