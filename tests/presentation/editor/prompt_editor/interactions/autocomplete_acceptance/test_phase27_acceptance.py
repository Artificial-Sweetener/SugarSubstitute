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

"""Baseline Phase 27 autocomplete behavior before SOC extraction."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)


from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptCommandResult,
)
from substitute.presentation.editor.prompt_editor.interactions.autocomplete_acceptance import (
    PromptAutocompleteAcceptanceController,
)
from substitute.presentation.editor.prompt_editor.models import AutocompleteSession


from tests.presentation.editor.prompt_editor.autocomplete.phase27_support import (
    _lora_item,
)


def test_phase27_acceptance_rejects_stale_source_and_commits_lora_after_success() -> (
    None
):
    """Autocomplete session acceptance should stay command-owned and stale-safe."""

    accepted: list[object] = []
    commit_calls = 0

    class _Editor:
        """Provide the command seam consumed by the acceptance controller."""

        def __init__(self) -> None:
            """Initialize current source identity."""

            self.identity = PromptSourceIdentity(
                source_revision=2,
                source_length=9,
            )

        def prompt_command_source_identity(self) -> PromptSourceIdentity:
            """Return current source identity."""

            return self.identity

        def execute_autocomplete_acceptance(
            self,
            acceptance: object,
        ) -> PromptCommandResult[object]:
            """Record one command-boundary acceptance."""

            accepted.append(acceptance)
            return PromptCommandResult.completed("accept_autocomplete")

        def commit_lora_autocomplete_replacement(self) -> None:
            """Record LoRA post-accept projection commit."""

            nonlocal commit_calls
            commit_calls += 1

    editor = _Editor()
    controller = PromptAutocompleteAcceptanceController(
        cursor_position=lambda: 0,
        current_source_identity=editor.prompt_command_source_identity,
        execute_acceptance=editor.execute_autocomplete_acceptance,
        complete_lora_replacement=editor.commit_lora_autocomplete_replacement,
    )
    stale_session = AutocompleteSession(
        suggestions=(PromptAutocompleteSuggestion("midna helmet"),),
        selected_index=0,
        word_start=0,
        word_end=5,
        active_tag_end=5,
        prefix="midna",
    )

    stale = controller.accept_session(
        stale_session,
        source_identity=PromptSourceIdentity(source_revision=1, source_length=9),
        add_comma=False,
    )

    assert stale.status == "rejected"
    assert stale.reason == "stale_source"
    assert accepted == []

    item = _lora_item()
    lora_session = AutocompleteSession(
        mode="lora",
        selected_index=0,
        lora_candidates=(
            PromptLoraAutocompleteCandidate(
                item=item,
                score=10,
                display_text="Midna",
                display_completion_suffix="na",
                replacement_text="<lora:midna:1>",
                match_kind="display",
            ),
        ),
        lora_query=PromptLoraAutocompleteQuery(
            query_text="mid",
            token_start=0,
            token_end=9,
            name_start=6,
            name_end=9,
            replacement_start=0,
            replacement_end=9,
            typed_weight_text=None,
            has_closing_bracket=False,
        ),
    )

    accepted_outcome = controller.accept_session(
        lora_session,
        source_identity=editor.identity,
        add_comma=False,
    )

    assert accepted_outcome.status == "accepted"
    assert len(accepted) == 1
    assert commit_calls == 1
