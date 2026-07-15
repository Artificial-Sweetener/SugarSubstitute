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

"""Detect repeated prompt segments in scene-effective prompt scopes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from substitute.domain.prompt import (
    PromptSceneBlock,
    PromptSceneDocument,
    SourceRange,
)

from .prompt_diagnostics_models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDuplicateSegmentDiagnosticPayload,
)
from .prompt_diagnostics_service import PromptDiagnosticProviderResult
from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_views import PromptDocumentView
from .prompt_scene_projection_service import parse_prompt_scene_projection_document

_MODELISH_SUFFIXES = (".safetensors", ".ckpt", ".pt", ".pth", ".onnx")
_HASH_RE = re.compile(r"^[a-f0-9]{8,}$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _DuplicateSegmentOccurrence:
    """Store one normalized segment occurrence and its source extent."""

    normalized_segment: str
    source_start: int
    source_end: int


class PromptDuplicateSegmentDiagnosticProvider:
    """Produce repeated-segment diagnostics within scene-effective prompt scopes."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
    ) -> None:
        """Store prompt parsing collaborators."""

        self._document_projector = document_projector or PromptDocumentProjector()

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Return duplicate-segment diagnostics for one prompt source string."""

        document_view = self._document_projector.build_document_view(text)
        scene_document = parse_prompt_scene_projection_document(text)
        diagnostics = (
            self._diagnostics_without_scenes(document_view)
            if not scene_document.has_scenes
            else self._diagnostics_for_scene_document(document_view, scene_document)
        )
        return PromptDiagnosticProviderResult(diagnostics=diagnostics)

    def _diagnostics_without_scenes(
        self,
        document_view: PromptDocumentView,
    ) -> tuple[PromptDiagnostic, ...]:
        """Return duplicate diagnostics for a single ordinary prompt scope."""

        occurrences = self._occurrences_in_range(
            document_view,
            SourceRange(0, len(document_view.source_text)),
        )
        return _diagnostics_for_occurrences(occurrences, first_occurrences={})

    def _diagnostics_for_scene_document(
        self,
        document_view: PromptDocumentView,
        scene_document: PromptSceneDocument,
    ) -> tuple[PromptDiagnostic, ...]:
        """Return duplicate diagnostics for universal plus independent scene scopes."""

        universal_occurrences = self._occurrences_in_range(
            document_view,
            scene_document.universal_range,
        )
        diagnostics = list(
            _diagnostics_for_occurrences(universal_occurrences, first_occurrences={})
        )
        universal_first_occurrences = _first_occurrence_map(universal_occurrences)
        for scene in scene_document.scenes:
            diagnostics.extend(
                self._diagnostics_for_scene_scope(
                    document_view,
                    scene=scene,
                    universal_first_occurrences=universal_first_occurrences,
                )
            )
        return tuple(diagnostics)

    def _diagnostics_for_scene_scope(
        self,
        document_view: PromptDocumentView,
        *,
        scene: PromptSceneBlock,
        universal_first_occurrences: dict[str, _DuplicateSegmentOccurrence],
    ) -> tuple[PromptDiagnostic, ...]:
        """Return diagnostics for one scene against universal and scene-local text."""

        scene_occurrences = self._occurrences_in_range(
            document_view,
            scene.content_range,
        )
        return _diagnostics_for_occurrences(
            scene_occurrences,
            first_occurrences=dict(universal_first_occurrences),
        )

    def _occurrences_in_range(
        self,
        document_view: PromptDocumentView,
        source_range: SourceRange,
    ) -> tuple[_DuplicateSegmentOccurrence, ...]:
        """Return eligible segment occurrences fully contained by one source range."""

        occurrences: list[_DuplicateSegmentOccurrence] = []
        for segment_range in _plain_segment_ranges(
            document_view.source_text,
            source_range,
        ):
            occurrence = self._occurrence_for_range(document_view, segment_range)
            if occurrence is not None:
                occurrences.append(occurrence)
        return tuple(occurrences)

    def _occurrence_for_range(
        self,
        document_view: PromptDocumentView,
        segment_range: SourceRange,
    ) -> _DuplicateSegmentOccurrence | None:
        """Return a normalized prompt segment occurrence when eligible."""

        if segment_range.start >= segment_range.end:
            return None
        if _segment_has_excluded_syntax(document_view, segment_range):
            return None
        source_text = segment_range.slice(document_view.source_text)
        segment_text = _extract_segment_text(source_text)
        if segment_text is None:
            return None
        normalized_segment = normalize_duplicate_prompt_segment(segment_text)
        if not normalized_segment or _looks_like_machine_text(normalized_segment):
            return None
        return _DuplicateSegmentOccurrence(
            normalized_segment=normalized_segment,
            source_start=segment_range.start,
            source_end=segment_range.end,
        )


def normalize_duplicate_prompt_segment(text: str) -> str:
    """Return a duplicate-detection key for one prompt segment string."""

    return " ".join(text.replace("_", " ").casefold().split())


def _diagnostics_for_occurrences(
    occurrences: tuple[_DuplicateSegmentOccurrence, ...],
    *,
    first_occurrences: dict[str, _DuplicateSegmentOccurrence],
) -> tuple[PromptDiagnostic, ...]:
    """Return duplicate diagnostics while updating one first-occurrence scope map."""

    diagnostics: list[PromptDiagnostic] = []
    for occurrence in occurrences:
        first_occurrence = first_occurrences.get(occurrence.normalized_segment)
        if first_occurrence is None:
            first_occurrences[occurrence.normalized_segment] = occurrence
            continue
        diagnostics.append(
            _diagnostic_for_duplicate(
                first_occurrence=first_occurrence,
                duplicate_occurrence=occurrence,
            )
        )
    return tuple(diagnostics)


def _first_occurrence_map(
    occurrences: tuple[_DuplicateSegmentOccurrence, ...],
) -> dict[str, _DuplicateSegmentOccurrence]:
    """Return first occurrence by normalized segment without producing diagnostics."""

    first_occurrences: dict[str, _DuplicateSegmentOccurrence] = {}
    for occurrence in occurrences:
        first_occurrences.setdefault(occurrence.normalized_segment, occurrence)
    return first_occurrences


def _diagnostic_for_duplicate(
    *,
    first_occurrence: _DuplicateSegmentOccurrence,
    duplicate_occurrence: _DuplicateSegmentOccurrence,
) -> PromptDiagnostic:
    """Build one duplicate-segment diagnostic for a later occurrence."""

    payload = PromptDuplicateSegmentDiagnosticPayload(
        normalized_segment=duplicate_occurrence.normalized_segment,
        first_source_start=first_occurrence.source_start,
        first_source_end=first_occurrence.source_end,
        duplicate_source_start=duplicate_occurrence.source_start,
        duplicate_source_end=duplicate_occurrence.source_end,
    )
    return PromptDiagnostic(
        diagnostic_id=(
            "duplicate-segment:"
            f"{duplicate_occurrence.source_start}:"
            f"{duplicate_occurrence.source_end}:"
            f"{duplicate_occurrence.normalized_segment}"
        ),
        kind=PromptDiagnosticKind.DUPLICATE_SEGMENT,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=duplicate_occurrence.source_start,
        source_end=duplicate_occurrence.source_end,
        message=f"Duplicate prompt segment: {duplicate_occurrence.normalized_segment}",
        payload=payload,
    )


def _segment_has_excluded_syntax(
    document_view: PromptDocumentView,
    segment_range: SourceRange,
) -> bool:
    """Return whether a segment contains syntax that is not a plain prompt segment."""

    for lora_span in document_view.lora_spans:
        if _ranges_overlap(
            segment_range.start,
            segment_range.end,
            lora_span.outer_start,
            lora_span.outer_end,
        ):
            return True
    for wildcard_span in document_view.wildcard_spans:
        if _ranges_overlap(
            segment_range.start,
            segment_range.end,
            wildcard_span.outer_start,
            wildcard_span.outer_end,
        ):
            return True
    return False


def _plain_segment_ranges(
    text: str, source_range: SourceRange
) -> tuple[SourceRange, ...]:
    """Return comma/newline-delimited plain prompt segment ranges."""

    ranges: list[SourceRange] = []
    segment_start = source_range.start
    for index in range(source_range.start, source_range.end):
        if text[index] in ",\n\r":
            segment_range = _trimmed_range(text, segment_start, index)
            if segment_range.start < segment_range.end:
                ranges.append(segment_range)
            segment_start = index + 1
    final_range = _trimmed_range(text, segment_start, source_range.end)
    if final_range.start < final_range.end:
        ranges.append(final_range)
    return tuple(ranges)


def _trimmed_range(text: str, start: int, end: int) -> SourceRange:
    """Return source range with horizontal and vertical whitespace stripped."""

    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return SourceRange(start, end)


def _extract_segment_text(source_text: str) -> str | None:
    """Return segment text after unwrapping supported emphasis wrappers."""

    current = source_text.strip()
    if not current:
        return None
    while _is_balanced_parenthesized(current):
        inner = current[1:-1].strip()
        weighted = _split_weighted_emphasis(inner)
        current = weighted[0] if weighted is not None else inner
        if not current:
            return None
    if any(character in current for character in "<>{}[]|\\"):
        return None
    if "\n" in current or "\r" in current:
        return None
    return current


def _is_balanced_parenthesized(text: str) -> bool:
    """Return whether text is fully wrapped by one balanced parenthesis pair."""

    if len(text) < 2 or text[0] != "(" or text[-1] != ")":
        return False
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0 and index != len(text) - 1:
                return False
        if depth < 0:
            return False
    return depth == 0


def _split_weighted_emphasis(text: str) -> tuple[str, Decimal] | None:
    """Return content and weight when text uses weighted emphasis syntax."""

    content, separator, raw_weight = text.rpartition(":")
    if not separator or not content or not raw_weight:
        return None
    try:
        weight = Decimal(raw_weight)
    except InvalidOperation:
        return None
    return content.strip(), weight


def _looks_like_machine_text(normalized_segment: str) -> bool:
    """Return whether normalized text is clearly not a plain prompt segment."""

    if "://" in normalized_segment:
        return True
    if "/" in normalized_segment or "\\" in normalized_segment:
        return True
    if normalized_segment.endswith(_MODELISH_SUFFIXES):
        return True
    if _HASH_RE.fullmatch(normalized_segment) is not None:
        return True
    return False


def _ranges_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    """Return whether two half-open ranges overlap."""

    return first_start < second_end and second_start < first_end


__all__ = [
    "PromptDuplicateSegmentDiagnosticProvider",
    "normalize_duplicate_prompt_segment",
]
