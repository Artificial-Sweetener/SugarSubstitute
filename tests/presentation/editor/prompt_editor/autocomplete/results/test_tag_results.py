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

from collections.abc import Hashable


from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteResultController,
    PromptAutocompleteResultSourceIdentity,
    PromptAutocompleteTagContext,
    PromptAutocompleteTriggerWordResult,
)
from tests.support.prompt_editor.autocomplete_support import (
    RecordingPromptAutocompleteGateway,
)


def test_phase27_tag_results_preserve_suffix_fallback_noop_filter_and_merge_order() -> (
    None
):
    """Tag autocomplete should preserve fallback, filtering, and trigger merge order."""

    gateway = RecordingPromptAutocompleteGateway(
        {
            "very long prompt 1g": (),
            "1g": (
                PromptAutocompleteSuggestion("1girl", 100),
                PromptAutocompleteSuggestion("1girls", 50),
            ),
        }
    )

    class _TriggerProvider:
        """Provide trigger-word rows that should merge before file rows."""

        def trigger_word_suggestions(
            self,
            prefix: str,
            prompt_text: str,
            *,
            source_text: str,
            source_identity: PromptAutocompleteResultSourceIdentity | None,
            query_identity: Hashable | None,
        ) -> PromptAutocompleteTriggerWordResult:
            """Return one duplicate row and one trigger-only row."""

            _ = (prompt_text, source_text, source_identity, query_identity)
            if prefix != "1g":
                return PromptAutocompleteTriggerWordResult(
                    suggestions=(),
                    scheduled_lora_signature=(),
                )
            return PromptAutocompleteTriggerWordResult(
                suggestions=(
                    PromptAutocompleteSuggestion(
                        "1girl",
                        popularity=None,
                        source_label="Trigger LoRA",
                        source_kind="lora_trigger",
                    ),
                    PromptAutocompleteSuggestion("1g trigger", popularity=None),
                ),
                scheduled_lora_signature=(("lora", "backend", "Trigger LoRA", (), ""),),
            )

    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        trigger_word_provider=_TriggerProvider(),
        limit=10,
    )
    source_text = "very long prompt 1g"

    result = controller.result_for_tag_query(
        PromptAutocompleteQuery(
            prefix=source_text,
            word_start=0,
            word_end=len(source_text),
            active_tag_end=len(source_text),
            fallback_query=PromptAutocompleteFallbackQuery(
                prefix="1g",
                word_start=source_text.rindex("1g"),
                word_end=len(source_text),
                active_tag_end=len(source_text),
            ),
        ),
        context=PromptAutocompleteTagContext(
            source_text=source_text,
            effective_prompt_text=source_text,
        ),
        source_identity=PromptSourceIdentity(
            source_revision=4,
            source_length=len(source_text),
        ),
    )

    assert gateway.calls == [(source_text, 10), ("1g", 10)]
    assert [suggestion.tag for suggestion in result.suggestions] == [
        "1girl",
        "1g trigger",
        "1girls",
    ]
    assert result.prefix == "1g"
    assert result.had_candidates is True

    no_op_result = controller.result_for_tag_query(
        PromptAutocompleteQuery(
            prefix="1girl",
            word_start=0,
            word_end=len("1girl"),
            active_tag_end=len("1girl"),
        ),
        context=PromptAutocompleteTagContext(
            source_text="1girl",
            effective_prompt_text="1girl",
        ),
        source_identity=PromptSourceIdentity(
            source_revision=5,
            source_length=len("1girl"),
        ),
    )

    assert all(suggestion.tag != "1girl" for suggestion in no_op_result.suggestions)
