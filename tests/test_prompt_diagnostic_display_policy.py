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

"""Contract tests for prompt diagnostic display policy."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptDiagnostic,
    PromptDiagnosticDisplayPolicy,
    PromptDiagnosticKind,
    PromptDiagnosticSeverity,
    PromptDiagnosticSnapshot,
    PromptSpellingDiagnosticPayload,
)


def test_display_policy_hides_spelling_diagnostic_containing_caret() -> None:
    """Active edited words should not show a spelling diagnostic."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")

    assert _visible_diagnostics("beut", (diagnostic,), cursor_position=2) == ()


def test_display_policy_hides_uncommitted_trailing_spelling_diagnostic() -> None:
    """Trailing active words should stay hidden until committed."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")

    assert _visible_diagnostics("beut", (diagnostic,), cursor_position=4) == ()


def test_display_policy_shows_spelling_diagnostic_after_space_boundary() -> None:
    """A space after the word commits it for diagnostic display."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")

    assert _visible_diagnostics("beut ", (diagnostic,), cursor_position=5) == (
        diagnostic,
    )


def test_display_policy_shows_spelling_diagnostic_after_comma_boundary() -> None:
    """A comma should commit prompt words even without a following space."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")

    assert _visible_diagnostics("beut,", (diagnostic,), cursor_position=5) == (
        diagnostic,
    )


def test_display_policy_shows_trailing_spelling_when_caret_moved_away() -> None:
    """A trailing misspelling should show once the caret is no longer editing it."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")

    assert _visible_diagnostics("beut", (diagnostic,), cursor_position=0) == (
        diagnostic,
    )


def test_display_policy_preserves_other_spelling_diagnostics() -> None:
    """Only the actively edited spelling diagnostic should be suppressed."""

    first = _spelling_diagnostic(0, 4, "wron")
    second = _spelling_diagnostic(5, 9, "beut")

    assert _visible_diagnostics("wron beut", (first, second), cursor_position=9) == (
        first,
    )


def test_display_policy_treats_plain_colon_as_commit_boundary() -> None:
    """A colon should commit prose spellcheck tokens outside skipped prompt syntax."""

    diagnostic = _spelling_diagnostic(0, 4, "beut")

    assert _visible_diagnostics("beut:", (diagnostic,), cursor_position=5) == (
        diagnostic,
    )


def _spelling_diagnostic(
    source_start: int,
    source_end: int,
    word: str,
) -> PromptDiagnostic:
    """Return one deterministic spelling diagnostic."""

    return PromptDiagnostic(
        diagnostic_id=f"spelling:{source_start}:{source_end}:{word}",
        kind=PromptDiagnosticKind.SPELLING,
        severity=PromptDiagnosticSeverity.ERROR,
        source_start=source_start,
        source_end=source_end,
        message=f"Possible spelling issue: {word}",
        payload=PromptSpellingDiagnosticPayload(word=word),
    )


def _visible_diagnostics(
    source_text: str,
    diagnostics: tuple[PromptDiagnostic, ...],
    *,
    cursor_position: int,
) -> tuple[PromptDiagnostic, ...]:
    """Return visible diagnostics for a deterministic policy test snapshot."""

    return PromptDiagnosticDisplayPolicy().visible_diagnostics(
        snapshot=PromptDiagnosticSnapshot(
            source_text=source_text,
            diagnostics=diagnostics,
        ),
        cursor_position=cursor_position,
    )
