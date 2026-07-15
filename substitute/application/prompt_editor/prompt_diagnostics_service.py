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

"""Coordinate enabled prompt diagnostic providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .prompt_diagnostics_models import PromptDiagnostic, PromptDiagnosticSnapshot


@dataclass(frozen=True, slots=True)
class PromptDiagnosticProviderResult:
    """Store one provider's diagnostic result."""

    diagnostics: tuple[PromptDiagnostic, ...]
    unavailable_reason: str | None = None


class PromptDiagnosticProvider(Protocol):
    """Produce diagnostics for one prompt source text."""

    def diagnostics_for_text(self, text: str) -> PromptDiagnosticProviderResult:
        """Return diagnostics for source text."""


class PromptDiagnosticsService:
    """Combine prompt diagnostics from enabled providers."""

    def __init__(
        self,
        providers: tuple[PromptDiagnosticProvider, ...],
    ) -> None:
        """Store enabled providers in deterministic execution order."""

        self._providers = providers

    def snapshot_for_text(self, text: str) -> PromptDiagnosticSnapshot:
        """Return a combined diagnostics snapshot for one source string."""

        diagnostics: list[PromptDiagnostic] = []
        unavailable_reasons: list[str] = []
        for provider in self._providers:
            result = provider.diagnostics_for_text(text)
            diagnostics.extend(result.diagnostics)
            if result.unavailable_reason is not None:
                unavailable_reasons.append(result.unavailable_reason)
        return PromptDiagnosticSnapshot(
            source_text=text,
            diagnostics=tuple(diagnostics),
            unavailable_reason=(
                None if not unavailable_reasons else "; ".join(unavailable_reasons)
            ),
        )


__all__ = [
    "PromptDiagnosticProvider",
    "PromptDiagnosticProviderResult",
    "PromptDiagnosticsService",
]
