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

from collections.abc import Sequence

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticPayload,
    PromptDuplicateSegmentDiagnosticPayload,
)


def remap_diagnostics_after_source_edit(
    diagnostics: Sequence[PromptDiagnostic],
    *,
    start: int,
    end: int,
    replacement_text: str,
) -> Sequence[PromptDiagnostic]:
    """Drop edit overlaps and shift unchanged downstream diagnostics."""

    delta = len(replacement_text) - (end - start)
    return tuple(
        remapped
        for diagnostic in diagnostics
        if (
            remapped := _remap_diagnostic(
                diagnostic,
                start=start,
                end=end,
                delta=delta,
            )
        )
        is not None
    )


def _remap_diagnostic(
    diagnostic: PromptDiagnostic,
    *,
    start: int,
    end: int,
    delta: int,
) -> PromptDiagnostic | None:
    """Return one shifted diagnostic or drop an edit overlap."""

    overlaps = (
        diagnostic.source_start <= start < diagnostic.source_end
        if start == end
        else diagnostic.source_start < end and start < diagnostic.source_end
    )
    if overlaps:
        return None
    if diagnostic.source_end <= start:
        return diagnostic

    return PromptDiagnostic(
        diagnostic_id=diagnostic.diagnostic_id,
        kind=diagnostic.kind,
        severity=diagnostic.severity,
        source_start=diagnostic.source_start + delta,
        source_end=diagnostic.source_end + delta,
        message=diagnostic.message,
        payload=_shift_diagnostic_payload(diagnostic.payload, delta=delta),
    )


def _shift_diagnostic_payload(
    payload: PromptDiagnosticPayload,
    *,
    delta: int,
) -> PromptDiagnosticPayload:
    """Return diagnostic payload ranges shifted by a uniform source delta."""

    if isinstance(payload, PromptDuplicateSegmentDiagnosticPayload):
        return PromptDuplicateSegmentDiagnosticPayload(
            normalized_segment=payload.normalized_segment,
            first_source_start=payload.first_source_start + delta,
            first_source_end=payload.first_source_end + delta,
            duplicate_source_start=payload.duplicate_source_start + delta,
            duplicate_source_end=payload.duplicate_source_end + delta,
        )
    return payload


__all__ = ["remap_diagnostics_after_source_edit"]
