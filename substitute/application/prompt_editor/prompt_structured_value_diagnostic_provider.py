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

"""Run prompt diagnostics against decoded structured-document values."""

from __future__ import annotations

from dataclasses import replace

from substitute.domain.prompt import SourceRange

from .prompt_diagnostics_service import (
    PromptDiagnosticProvider,
    PromptDiagnosticProviderResult,
)
from .prompt_document_semantics import PromptDocumentSemantics


class PromptStructuredValueDiagnosticProvider:
    """Map one prompt diagnostic provider through structured source values."""

    def __init__(
        self,
        *,
        provider: PromptDiagnosticProvider,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Store the provider and structured source mapping owner."""

        self._provider = provider
        self._document_semantics = document_semantics

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Diagnose decoded values and map results to exact source ranges."""

        if not self._document_semantics.uses_structured_prompt_values:
            return self._provider.diagnostics_for_text(text)
        diagnostics = []
        unavailable_reasons: list[str] = []
        for mapping in self._document_semantics.value_mappings_for_text(text):
            result = self._provider.diagnostics_for_text(mapping.logical_text)
            for diagnostic in result.diagnostics:
                if not (
                    0
                    <= diagnostic.source_start
                    <= diagnostic.source_end
                    <= len(mapping.logical_text)
                ):
                    continue
                source_range = mapping.source_range_for_logical_range(
                    SourceRange(diagnostic.source_start, diagnostic.source_end)
                )
                diagnostics.append(
                    replace(
                        diagnostic,
                        diagnostic_id=(
                            f"{mapping.value_id}:{diagnostic.diagnostic_id}"
                        ),
                        source_start=source_range.start,
                        source_end=source_range.end,
                    )
                )
            if result.unavailable_reason is not None:
                unavailable_reasons.append(result.unavailable_reason)
        return PromptDiagnosticProviderResult(
            diagnostics=tuple(diagnostics),
            unavailable_reason=(
                None
                if not unavailable_reasons
                else "; ".join(dict.fromkeys(unavailable_reasons))
            ),
        )


__all__ = ["PromptStructuredValueDiagnosticProvider"]
