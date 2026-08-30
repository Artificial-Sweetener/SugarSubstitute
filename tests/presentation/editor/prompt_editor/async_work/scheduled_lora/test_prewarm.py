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

"""Verify scheduled-LoRA context prewarm behavior at its async-work owner."""

from __future__ import annotations

from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from tests.support.prompt_editor.autocomplete_support import (
    build_test_autocomplete_stack,
)
from tests.support.prompt_editor.controller_support import (
    DeferredScheduledLoraContextProvider,
    EmptyAutocompleteGateway,
    TextAutocompleteEditorDouble,
)


def test_prewarm_scheduled_lora_context_caches_full_scheduled_loras() -> None:
    """Populate the full menu-readable cache through deferred prewarm work."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("midna helmet",),
        source="inline_prompt",
    )
    resolver_calls: list[str] = []

    def resolve_scheduled_loras(
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...]:
        """Record the deferred resolver call and return one scheduled LoRA."""

        resolver_calls.append(prompt_text)
        return (scheduled_lora,)

    provider = DeferredScheduledLoraContextProvider(resolve_scheduled_loras)
    _ = build_test_autocomplete_stack(
        TextAutocompleteEditorDouble("mid"),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        scheduled_lora_context_provider=provider,
    )

    assert provider.prewarm("mid") is True
    assert provider.prewarm("mid") is False
    assert len(provider.jobs) == 1
    assert resolver_calls == []
    assert provider.cached_scheduled_loras("mid") is None

    provider.complete()

    assert resolver_calls == ["mid"]
    assert provider.cached_scheduled_loras("mid") == (scheduled_lora,)
    assert provider.prewarm("mid") is False


def test_prewarm_scheduled_lora_context_requires_async_trigger_context() -> None:
    """Schedule scheduled-LoRA prewarm only through the async trigger path."""

    provider = DeferredScheduledLoraContextProvider(lambda _text: ())
    _ = build_test_autocomplete_stack(
        TextAutocompleteEditorDouble("mid"),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        limit=10,
    )
    _ = build_test_autocomplete_stack(
        TextAutocompleteEditorDouble("mid"),
        prompt_autocomplete_gateway=EmptyAutocompleteGateway(),
        limit=10,
        scheduled_lora_context_provider=provider,
        trigger_word_suggestions_enabled=False,
    )

    assert provider.jobs == []
