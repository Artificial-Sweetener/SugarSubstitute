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

"""Verify asynchronous scheduled-LoRA trigger freshness behavior."""

from __future__ import annotations


from types import SimpleNamespace
from typing import Any, cast

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    DeferredScheduledLoraContextProvider,
    TextAutocompleteEditorDouble,
)


from tests.presentation.editor.prompt_editor.autocomplete.results.result_controller_support import (
    _RecordingAutocompletePresenter,
    _mute_autocomplete_surfaces,
    _refresh_tag_result,
)


def test_coordinator_uses_static_tags_while_trigger_context_resolves() -> None:
    """Cold async trigger-word context does not block static tag autocomplete."""

    editor = TextAutocompleteEditorDouble("mid")
    resolver_calls: list[str] = []

    def resolve_scheduled_loras(prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record one resolver call while returning no LoRAs."""

        resolver_calls.append(prompt_text)
        return ()

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("mid shot", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )

    assert resolver_calls == []
    assert len(provider.jobs) == 1
    assert coordinator.session_controller.session.suggestions == (
        PromptAutocompleteSuggestion("mid shot", 200),
    )


def test_coordinator_skips_duplicate_refresh_for_empty_async_trigger_context() -> None:
    """Empty async trigger-word results do not redraw unchanged tag suggestions."""

    editor = TextAutocompleteEditorDouble("mid")
    provider = DeferredScheduledLoraContextProvider(lambda _text: ())
    presenter = _RecordingAutocompletePresenter()
    coordinator = cast(
        Any,
        build_test_autocomplete_stack(
            editor,
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("mid shot", 200),
                )
            ),
            scheduled_lora_context_provider=provider,
            autocomplete_presenter=cast(Any, presenter),
        ),
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    provider.complete()

    assert presenter.presented_sessions == [coordinator.session_controller.session]
    assert coordinator.session_controller.session.suggestions == (
        PromptAutocompleteSuggestion("mid shot", 200),
    )


def test_coordinator_applies_async_trigger_words_for_current_query() -> None:
    """Completed async trigger-word context refreshes the current tag session."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    editor = TextAutocompleteEditorDouble("mid")
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda _prefix, limit=10: (
                        PromptAutocompleteSuggestion("mid shot", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    provider.complete()

    assert [
        (suggestion.tag, suggestion.source_label, suggestion.source_kind)
        for suggestion in coordinator.session_controller.session.suggestions
    ] == [
        ("midna helmet", "Friendly Midna", "lora_trigger"),
        ("mid shot", None, "tag"),
    ]


def test_coordinator_discards_stale_async_trigger_words() -> None:
    """Older async trigger-word results must not replace the active tag query."""

    stale_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    current_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("ranni hat",),
        source="inline_prompt",
    )
    editor = TextAutocompleteEditorDouble("mid")
    resolver_results = [(stale_lora,), (current_lora,)]

    def resolve_scheduled_loras(_text: str) -> tuple[PromptScheduledLora, ...]:
        """Return queued scheduled-LoRA results in request order."""

        return resolver_results.pop(0)

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                editor,
                prompt_autocomplete_gateway=SimpleNamespace(
                    search=lambda prefix, limit=10: (
                        PromptAutocompleteSuggestion(f"{prefix} static", 200),
                    )
                ),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    editor.text = "ran"
    editor.source_revision += 1
    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="ran",
            word_start=0,
            word_end=3,
            active_tag_end=3,
        ),
        source_text=editor.text,
    )
    provider.complete(index=0)

    assert [
        suggestion.tag
        for suggestion in coordinator.session_controller.session.suggestions
    ] == ["ran static"]

    provider.complete(index=0)

    assert [
        suggestion.tag
        for suggestion in coordinator.session_controller.session.suggestions
    ] == [
        "ranni hat",
        "ran static",
    ]
