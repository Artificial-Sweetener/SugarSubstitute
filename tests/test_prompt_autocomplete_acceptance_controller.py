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

"""Cover command-owned autocomplete acceptance boundaries."""

from __future__ import annotations

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandResult,
    PromptTagAutocompleteAcceptance,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance import (
    PromptAutocompleteAcceptanceController,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession


class _Cursor:
    """Expose the cursor position used by tag acceptance fallback."""

    def position(self) -> int:
        """Return a deterministic cursor position."""

        return 5


class _Editor:
    """Record acceptance command execution without mutating source."""

    def __init__(
        self,
        command_result: PromptCommandResult[object] | None = None,
    ) -> None:
        """Store the command result returned by this test double."""

        self.accepted: list[object] = []
        self.command_result = command_result or PromptCommandResult.completed(
            "accept_autocomplete"
        )

    def textCursor(self) -> _Cursor:  # noqa: N802
        """Return the live cursor adapter used by acceptance."""

        return _Cursor()

    def prompt_command_source_identity(self) -> None:
        """Return no source identity for tests that do not need staleness."""

        return None

    def execute_autocomplete_acceptance(
        self,
        acceptance: object,
    ) -> PromptCommandResult[object]:
        """Record a command-boundary acceptance and return the configured result."""

        self.accepted.append(acceptance)
        return self.command_result

    def commit_lora_autocomplete_replacement(self) -> None:
        """Fail if tag acceptance tries to commit LoRA projection state."""

        raise AssertionError("tag acceptance should not commit LoRA state")


def test_acceptance_controller_rejects_missing_selection_before_command() -> None:
    """Acceptance should fail closed when the session has no selected suggestion."""

    editor = _Editor()
    controller = PromptAutocompleteAcceptanceController(editor=editor)

    outcome = controller.accept_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("alpha"),),
            selected_index=-1,
            word_start=0,
            word_end=5,
            prefix="alpha",
        ),
        source_identity=None,
        add_comma=False,
    )

    assert outcome.status == "rejected"
    assert outcome.reason == "missing_selection"
    assert editor.accepted == []


def test_acceptance_controller_propagates_command_rejection() -> None:
    """Command rejection should flow back through the acceptance outcome."""

    editor = _Editor(
        PromptCommandResult.rejected(
            "accept_autocomplete",
            reason="stale_source",
        )
    )
    controller = PromptAutocompleteAcceptanceController(editor=editor)

    outcome = controller.accept_session(
        AutocompleteSession(
            mode="tag",
            suggestions=(PromptAutocompleteSuggestion("alpha"),),
            selected_index=0,
            word_start=0,
            word_end=5,
            prefix="alpha",
        ),
        source_identity=None,
        add_comma=True,
    )

    assert outcome.status == "rejected"
    assert outcome.reason == "stale_source"
    assert editor.accepted == [
        PromptTagAutocompleteAcceptance(
            tag="alpha",
            prefix="alpha",
            word_start=0,
            word_end=5,
            active_tag_end=5,
            add_comma=True,
        )
    ]
