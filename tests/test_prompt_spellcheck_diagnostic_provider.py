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

"""Contract tests for spellcheck-to-diagnostic provider adaptation."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor import (
    PromptDiagnosticKind,
    PromptSpellcheckDiagnosticProvider,
    PromptSpellcheckService,
    PromptSpellcheckSnapshot,
    PromptSpellingDiagnosticPayload,
    PromptSpellingIssue,
)


class _FakeSpellcheckService:
    """Provide deterministic spellcheck snapshots for provider tests."""

    language_tag = "en_US"

    def __init__(self, snapshot: PromptSpellcheckSnapshot) -> None:
        """Store the configured snapshot."""

        self._snapshot = snapshot

    def snapshot_for_text(self, text: str) -> PromptSpellcheckSnapshot:
        """Return the configured snapshot while preserving call shape."""

        _ = text
        return self._snapshot


def test_spellcheck_provider_converts_issues_to_prompt_diagnostics() -> None:
    """Spellcheck ranges and words should become generic diagnostics."""

    provider = PromptSpellcheckDiagnosticProvider(
        cast(
            PromptSpellcheckService,
            _FakeSpellcheckService(
                PromptSpellcheckSnapshot(
                    source_text="beut",
                    language_tag="en_US",
                    issues=(PromptSpellingIssue(0, 4, "beut"),),
                )
            ),
        )
    )

    snapshot = provider.snapshot_for_text("beut")

    assert snapshot.source_text == "beut"
    assert snapshot.unavailable_reason is None
    assert len(snapshot.diagnostics) == 1
    diagnostic = snapshot.diagnostics[0]
    assert diagnostic.diagnostic_id == "spelling:0:4:beut"
    assert diagnostic.kind is PromptDiagnosticKind.SPELLING
    assert diagnostic.source_start == 0
    assert diagnostic.source_end == 4
    assert diagnostic.payload == PromptSpellingDiagnosticPayload(word="beut")


def test_spellcheck_provider_preserves_unavailable_reason() -> None:
    """Backend unavailability should survive provider adaptation."""

    provider = PromptSpellcheckDiagnosticProvider(
        cast(
            PromptSpellcheckService,
            _FakeSpellcheckService(
                PromptSpellcheckSnapshot(
                    source_text="text",
                    language_tag="en_US",
                    issues=(),
                    unavailable_reason="No backend.",
                )
            ),
        )
    )

    snapshot = provider.snapshot_for_text("text")

    assert snapshot.diagnostics == ()
    assert snapshot.unavailable_reason == "No backend."
