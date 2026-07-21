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

"""Report scene markers rejected by active prompt-document semantics."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage, app_text

from .prompt_diagnostics_models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptUnsupportedSceneMarkerDiagnosticPayload,
)
from .prompt_diagnostics_service import PromptDiagnosticProviderResult
from .prompt_document_semantics import PromptDocumentSemantics

UNSUPPORTED_SCENE_MARKER_MESSAGE: ApplicationMessage = app_text(
    "Scenes aren’t supported in wildcard values."
)


class PromptUnsupportedSceneMarkerDiagnosticProvider:
    """Produce exact errors for unsupported leading scene markers."""

    def __init__(self, *, document_semantics: PromptDocumentSemantics) -> None:
        """Store the semantics that authoritatively identify invalid markers."""

        self._document_semantics = document_semantics

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Return one non-ignorable diagnostic for each rejected scene marker."""

        diagnostics = tuple(
            PromptDiagnostic(
                diagnostic_id=f"unsupported-scene-marker:{source_range.start}",
                kind=PromptDiagnosticKind.UNSUPPORTED_SCENE_MARKER,
                severity=PromptDiagnosticSeverity.ERROR,
                source_start=source_range.start,
                source_end=source_range.end,
                message=UNSUPPORTED_SCENE_MARKER_MESSAGE,
                payload=PromptUnsupportedSceneMarkerDiagnosticPayload(),
            )
            for source_range in self._document_semantics.unsupported_scene_marker_ranges(
                text
            )
        )
        return PromptDiagnosticProviderResult(diagnostics=diagnostics)


__all__ = [
    "PromptUnsupportedSceneMarkerDiagnosticProvider",
    "UNSUPPORTED_SCENE_MARKER_MESSAGE",
]
