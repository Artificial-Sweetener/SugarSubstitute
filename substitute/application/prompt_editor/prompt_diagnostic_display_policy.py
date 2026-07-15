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

"""Choose prompt diagnostics visible for the current editor state."""

from __future__ import annotations

from .prompt_diagnostics_models import (
    PromptDiagnostic,
    PromptDiagnosticKind,
    PromptDiagnosticSnapshot,
)

_COMMIT_BOUNDARIES = frozenset(",;:.!?)]}\"'")


class PromptDiagnosticDisplayPolicy:
    """Filter diagnostics that should be hidden while editing is active."""

    def visible_diagnostics(
        self,
        *,
        snapshot: PromptDiagnosticSnapshot,
        cursor_position: int,
    ) -> tuple[PromptDiagnostic, ...]:
        """Return diagnostics visible for the current source caret position."""

        bounded_cursor = max(0, min(cursor_position, len(snapshot.source_text)))
        return tuple(
            diagnostic
            for diagnostic in snapshot.diagnostics
            if not _diagnostic_is_active(
                diagnostic,
                source_text=snapshot.source_text,
                cursor_position=bounded_cursor,
            )
        )


def _diagnostic_is_active(
    diagnostic: PromptDiagnostic,
    *,
    source_text: str,
    cursor_position: int,
) -> bool:
    """Return whether the diagnostic should be hidden during active editing."""

    if diagnostic.kind is PromptDiagnosticKind.WILDCARD:
        return _wildcard_diagnostic_is_active(
            diagnostic,
            source_text=source_text,
            cursor_position=cursor_position,
        )
    if diagnostic.kind is not PromptDiagnosticKind.SPELLING:
        return False
    if diagnostic.source_start < cursor_position < diagnostic.source_end:
        return True
    if cursor_position != diagnostic.source_end:
        return False
    if diagnostic.source_end >= len(source_text):
        return True
    return not _is_word_boundary(source_text[diagnostic.source_end])


def _wildcard_diagnostic_is_active(
    diagnostic: PromptDiagnostic,
    *,
    source_text: str,
    cursor_position: int,
) -> bool:
    """Return whether a missing wildcard should stay quiet while being edited."""

    if diagnostic.source_start < cursor_position < diagnostic.source_end:
        return True
    if cursor_position != diagnostic.source_end:
        return False
    if diagnostic.source_end >= len(source_text):
        return True
    return not _is_word_boundary(source_text[diagnostic.source_end])


def _is_word_boundary(character: str) -> bool:
    """Return whether a character commits the preceding spellcheck token."""

    return character.isspace() or character in _COMMIT_BOUNDARIES


__all__ = ["PromptDiagnosticDisplayPolicy"]
