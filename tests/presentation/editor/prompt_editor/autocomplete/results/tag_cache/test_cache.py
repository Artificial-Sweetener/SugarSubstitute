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

"""Verify tag autocomplete result-cache contracts."""

from __future__ import annotations


from substitute.application.ports import (
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
)
from substitute.presentation.editor.prompt_editor.features.autocomplete_result_controller import (
    _AUTOCOMPLETE_RESULT_CACHE_LIMIT,
    PromptAutocompleteResultController,
)


from tests.presentation.editor.prompt_editor.autocomplete.results.result_controller_support import (
    _Gateway,
    _TriggerProvider,
    _source_identity,
    _tag_context,
    _tag_query,
)


def test_tag_results_preserve_cache_identity_and_eviction() -> None:
    """Tag result caching is source-aware and bounded."""

    gateway = _Gateway(
        {
            "ha": (PromptAutocompleteSuggestion("hair ornament", 100),),
            **{
                f"h{index}": (PromptAutocompleteSuggestion(f"h{index} completion", 1),)
                for index in range(_AUTOCOMPLETE_RESULT_CACHE_LIMIT + 2)
            },
        }
    )
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        limit=10,
    )

    first = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(1, 2),
    )
    second = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(1, 2),
    )
    changed_source = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(2, 2),
    )

    assert gateway.calls[:2] == [("ha", 10), ("ha", 10)]
    assert first.cache_key == second.cache_key
    assert second.cache_key != changed_source.cache_key

    first_evicted_key = None
    for index in range(_AUTOCOMPLETE_RESULT_CACHE_LIMIT + 2):
        prefix = f"h{index}"
        result = controller.result_for_tag_query(
            _tag_query(prefix),
            context=_tag_context(prefix),
            source_identity=_source_identity(index + 10, len(prefix)),
        )
        if index == 0:
            first_evicted_key = result.cache_key

    assert controller.cached_tag_result_count == _AUTOCOMPLETE_RESULT_CACHE_LIMIT
    assert first_evicted_key not in controller.cached_tag_result_keys()


def test_tag_result_cache_misses_when_trigger_signature_changes() -> None:
    """Scheduled-LoRA trigger signatures participate in tag result cache identity."""

    gateway = _Gateway({"ha": (PromptAutocompleteSuggestion("hair ornament", 4100),)})
    trigger_provider = _TriggerProvider()
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        trigger_word_provider=trigger_provider,
        limit=10,
    )

    first = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(8, 2),
    )
    second = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(8, 2),
    )
    trigger_provider.signature = (
        ("inline_prompt", "midna", "Friendly Midna", ("midna helmet",), "midna"),
    )
    third = controller.result_for_tag_query(
        _tag_query("ha"),
        context=_tag_context("ha"),
        source_identity=_source_identity(8, 2),
    )

    assert gateway.calls == [("ha", 10), ("ha", 10)]
    assert first.cache_key == second.cache_key
    assert second.cache_key != third.cache_key


def test_tag_results_preserve_fallback_filtering_trigger_merge_and_signature() -> None:
    """Tag results preserve fallback, no-op filtering, trigger ordering, and signatures."""

    gateway = _Gateway(
        {
            "very long prompt 1g": (),
            "1g": (
                PromptAutocompleteSuggestion("1girl", 100),
                PromptAutocompleteSuggestion("1girls", 50),
            ),
        }
    )
    trigger_provider = _TriggerProvider(
        rows=(
            PromptAutocompleteSuggestion(
                "1girl",
                popularity=None,
                source_label="Trigger LoRA",
                source_kind="lora_trigger",
            ),
            PromptAutocompleteSuggestion("1g trigger", popularity=None),
        ),
        signature=(("lora", "backend", "Trigger LoRA", (), ""),),
    )
    controller = PromptAutocompleteResultController(
        prompt_autocomplete_gateway=gateway,
        trigger_word_provider=trigger_provider,
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
        context=_tag_context(source_text, effective_text="scene effective 1g"),
        source_identity=_source_identity(4, len(source_text)),
    )
    no_op_result = controller.result_for_tag_query(
        _tag_query("1girl"),
        context=_tag_context("1girl"),
        source_identity=_source_identity(5, len("1girl")),
    )

    assert gateway.calls == [(source_text, 10), ("1g", 10), ("1girl", 10)]
    assert [suggestion.tag for suggestion in result.suggestions] == [
        "1girl",
        "1g trigger",
        "1girls",
    ]
    assert result.prefix == "1g"
    assert result.had_candidates is True
    assert trigger_provider.calls[1][1] == "scene effective 1g"
    assert all(suggestion.tag != "1girl" for suggestion in no_op_result.suggestions)
