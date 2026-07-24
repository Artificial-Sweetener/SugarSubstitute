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

"""Define generic prompt diagnostics in raw prompt source coordinates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sugarsubstitute_shared.localization import ApplicationText


class PromptDiagnosticKind(Enum):
    """Identify the source and action family of one prompt diagnostic."""

    SPELLING = "spelling"
    DUPLICATE_SEGMENT = "duplicate_segment"
    UNSUPPORTED_SCENE_MARKER = "unsupported_scene_marker"
    WILDCARD = "wildcard"


class PromptDiagnosticSeverity(Enum):
    """Describe diagnostic visual severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class PromptSpellingDiagnosticPayload:
    """Carry spelling-specific diagnostic data."""

    word: str


@dataclass(frozen=True, slots=True)
class PromptDuplicateSegmentDiagnosticPayload:
    """Carry duplicate-segment diagnostic data and edit targets."""

    normalized_segment: str
    first_source_start: int
    first_source_end: int
    duplicate_source_start: int
    duplicate_source_end: int


@dataclass(frozen=True, slots=True)
class PromptWildcardDiagnosticPayload:
    """Carry missing wildcard diagnostic metadata."""

    identifier: str
    wildcard_form: str
    csv_column: str | None = None
    matched_csv_column: str | None = None
    available_csv_columns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptUnsupportedSceneMarkerDiagnosticPayload:
    """Identify a scene marker rejected by the active document semantics."""

    marker: str = "**"


PromptDiagnosticPayload = (
    PromptSpellingDiagnosticPayload
    | PromptDuplicateSegmentDiagnosticPayload
    | PromptUnsupportedSceneMarkerDiagnosticPayload
    | PromptWildcardDiagnosticPayload
)


@dataclass(frozen=True, slots=True)
class PromptDiagnostic:
    """Describe one prompt diagnostic in raw source coordinates."""

    diagnostic_id: str
    kind: PromptDiagnosticKind
    severity: PromptDiagnosticSeverity
    source_start: int
    source_end: int
    message: ApplicationText
    payload: PromptDiagnosticPayload

    def __post_init__(self) -> None:
        """Reject invalid source ranges early."""

        if self.source_start < 0:
            raise ValueError("PromptDiagnostic.source_start must be non-negative.")
        if self.source_end < self.source_start:
            raise ValueError(
                "PromptDiagnostic.source_end must be greater than or equal to start."
            )


@dataclass(frozen=True, slots=True)
class PromptDiagnosticSnapshot:
    """Store diagnostics for one prompt source revision."""

    source_text: str
    diagnostics: tuple[PromptDiagnostic, ...]
    unavailable_reason: str | None = None


__all__ = [
    "PromptDiagnostic",
    "PromptDiagnosticKind",
    "PromptDiagnosticPayload",
    "PromptDiagnosticSeverity",
    "PromptDiagnosticSnapshot",
    "PromptDuplicateSegmentDiagnosticPayload",
    "PromptSpellingDiagnosticPayload",
    "PromptUnsupportedSceneMarkerDiagnosticPayload",
    "PromptWildcardDiagnosticPayload",
]
