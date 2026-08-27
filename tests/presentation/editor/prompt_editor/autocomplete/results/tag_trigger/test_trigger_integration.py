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

"""Verify tag autocomplete scheduled-LoRA trigger integration."""

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
from substitute.application.prompt_editor.scenes.projection import (
    effective_prompt_text_at_source_position,
)
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    DeferredScheduledLoraContextProvider,
    EmptyAutocompleteGateway,
    TextAutocompleteEditorDouble,
    scene_feature,
)


from tests.presentation.editor.prompt_editor.autocomplete.results.result_controller_support import (
    _mute_autocomplete_surfaces,
    _refresh_tag_result,
)


def test_coordinator_merges_lora_trigger_suggestions_before_static_tags() -> None:
    """Scheduled-LoRA trigger words are ranked before static tag matches."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    provider.cache_prompt("mid")
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                SimpleNamespace(toPlainText=lambda: "mid"),
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
        source_text="mid",
    )

    assert [
        (suggestion.tag, suggestion.source_label, suggestion.source_kind)
        for suggestion in coordinator.session_controller.session.suggestions
    ] == [
        ("midna helmet", "Friendly Midna", "lora_trigger"),
        ("mid shot", None, "tag"),
    ]


def test_coordinator_dedupes_static_tag_when_lora_trigger_matches() -> None:
    """Duplicate static tags collapse into the scheduled-LoRA trigger row."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    provider.cache_prompt("mid")
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            TextAutocompleteEditorDouble("mid"),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("midna_helmet", 200),
                )
            ),
            scheduled_lora_context_provider=provider,
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
        source_text="mid",
    )

    assert coordinator.session_controller.session.suggestions == (
        PromptAutocompleteSuggestion(
            "midna helmet",
            popularity=None,
            source_label="Friendly Midna",
            source_kind="lora_trigger",
        ),
    )


def test_coordinator_dedupes_static_tag_when_split_lora_trigger_matches() -> None:
    """Split CivitAI trigger parts still replace duplicate static tag rows."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("ranni elden ring, witch hat",),
        source="inline_prompt",
    )
    provider = DeferredScheduledLoraContextProvider(lambda _text: (scheduled_lora,))
    provider.cache_prompt("witch")
    coordinator = _mute_autocomplete_surfaces(
        build_test_autocomplete_stack(
            TextAutocompleteEditorDouble("witch"),
            prompt_autocomplete_gateway=SimpleNamespace(
                search=lambda _prefix, limit=10: (
                    PromptAutocompleteSuggestion("witch_hat", 200),
                )
            ),
            scheduled_lora_context_provider=provider,
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="witch",
            word_start=0,
            word_end=5,
            active_tag_end=5,
        ),
        source_text="witch",
    )

    assert coordinator.session_controller.session.suggestions == (
        PromptAutocompleteSuggestion(
            "witch hat",
            popularity=None,
            source_label="Ranni XL",
            source_kind="lora_trigger",
        ),
    )


def test_coordinator_uses_scene_effective_lora_trigger_context() -> None:
    """Scene-local trigger suggestions come from the active scene context."""

    global_lora = PromptScheduledLora(
        prompt_name="global",
        backend_value="global.safetensors",
        display_name="Global LoRA",
        trained_words=("midna global",),
        source="inline_prompt",
    )
    portrait_lora = PromptScheduledLora(
        prompt_name="portrait",
        backend_value="portrait.safetensors",
        display_name="Portrait LoRA",
        trained_words=("midna portrait",),
        source="inline_prompt",
    )
    source = "<lora:global:1>\n**portrait\n<lora:portrait:1>\nmid\n**cafe\nmid"
    resolver_calls: list[str] = []

    def resolve_scheduled_loras(
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return LoRAs visible from the effective prompt text."""

        resolver_calls.append(prompt_text)
        loras = [global_lora]
        if "<lora:portrait:1>" in prompt_text:
            loras.append(portrait_lora)
        return tuple(loras)

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    portrait_mid = source.index("mid")
    cafe_mid = source.rindex("mid")
    provider.cache_prompt(
        effective_prompt_text_at_source_position(
            text=source,
            source_position=portrait_mid,
        )
    )
    provider.cache_prompt(
        effective_prompt_text_at_source_position(
            text=source,
            source_position=cafe_mid,
        )
    )
    coordinator = _mute_autocomplete_surfaces(
        cast(
            Any,
            build_test_autocomplete_stack(
                TextAutocompleteEditorDouble(source),
                prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
                scene_publication=scene_feature(text=source, titles=()),
                scheduled_lora_context_provider=provider,
            ),
        )
    )

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=portrait_mid,
            word_end=portrait_mid + 3,
            active_tag_end=portrait_mid + 3,
        ),
        source_text=source,
    )

    assert [
        suggestion.tag
        for suggestion in coordinator.session_controller.session.suggestions
    ] == [
        "midna global",
        "midna portrait",
    ]

    _refresh_tag_result(
        coordinator,
        PromptAutocompleteQuery(
            prefix="mid",
            word_start=cafe_mid,
            word_end=cafe_mid + 3,
            active_tag_end=cafe_mid + 3,
        ),
        source_text=source,
    )

    assert [
        suggestion.tag
        for suggestion in coordinator.session_controller.session.suggestions
    ] == [
        "midna global",
    ]
    assert "<lora:portrait:1>" in resolver_calls[0]
    assert "<lora:portrait:1>" not in resolver_calls[1]
