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

"""Contract tests for Phase 27.5 autocomplete context owners."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Callable, Hashable

import pytest

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAutocompleteTriggerWordResult as AsyncTriggerWordResult,
    scheduled_lora_signature,
)
from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraCachedContextSnapshot,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteScheduledLoraContextController,
)


class _ScheduledCurrentContext:
    """Expose live source/query identity to scheduled-LoRA context tests."""

    def __init__(self) -> None:
        """Initialize deterministic live context state."""

        self.source_identity = PromptSourceIdentity(
            source_revision=8,
            source_length=3,
        )
        self.query_identity: Hashable | None = ("tag", "mid")
        self.refresh_calls = 0

    def current_source_identity(self) -> PromptSourceIdentity | None:
        """Return the live source identity."""

        return self.source_identity

    def current_query_identity(self) -> Hashable | None:
        """Return the live query identity."""

        return self.query_identity

    def refresh_current_query(self) -> None:
        """Record one scheduled-LoRA publication refresh."""

        self.refresh_calls += 1


class _ScheduledContextProvider:
    """Record scheduled-LoRA context owner calls without resolving async work."""

    def __init__(self) -> None:
        """Initialize provider call storage."""

        self.prewarm_calls: list[str] = []
        self.trigger_source_identity: PromptSourceIdentity | None = None
        self.trigger_current_source_identity: PromptSourceIdentity | None = None
        self.trigger_current_source_text: Callable[[], str] | None = None
        self.scheduled_lora = PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("midna helmet",),
            source="inline_prompt",
        )

    def prewarm(self, prompt_text: str) -> bool:
        """Record one prewarm request."""

        self.prewarm_calls.append(prompt_text)
        return True

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return cached scheduled LoRAs for one prompt."""

        if prompt_text != "mid":
            return None
        return (self.scheduled_lora,)

    def cached_context_snapshot(
        self,
        prompt_text: str,
    ) -> PromptScheduledLoraCachedContextSnapshot | None:
        """Return cached scheduled-LoRA identity for one prompt."""

        loras = self.cached_scheduled_loras(prompt_text)
        if loras is None:
            return None
        return PromptScheduledLoraCachedContextSnapshot(
            cache_key=("test", prompt_text),
            prompt_context_token=("test", len(prompt_text), hash(prompt_text)),
            scheduled_loras=loras,
            signature=scheduled_lora_signature(loras),
        )

    def trigger_word_result(
        self,
        *,
        prefix: str,
        prompt_text: str,
        source_text: str,
        source_identity: PromptSourceIdentity | None,
        query_identity: Hashable | None,
        current_source_text: Callable[[], str] | None,
        current_query_identity: Callable[[], Hashable | None],
        refresh_current_query: Callable[[], None],
        current_source_identity: Callable[[], PromptSourceIdentity | None]
        | None = None,
    ) -> AsyncTriggerWordResult:
        """Return deterministic trigger rows and record stale-safety callbacks."""

        _ = (prefix, prompt_text, source_text, query_identity)
        self.trigger_source_identity = source_identity
        self.trigger_current_source_text = current_source_text
        self.trigger_current_source_identity = (
            None if current_source_identity is None else current_source_identity()
        )
        assert current_query_identity() == ("tag", "mid")
        refresh_current_query()
        return AsyncTriggerWordResult(
            suggestions=(
                PromptAutocompleteSuggestion(
                    "midna helmet",
                    popularity=None,
                    source_label="Friendly Midna",
                    source_kind="lora_trigger",
                ),
            ),
            scheduled_lora_signature=scheduled_lora_signature((self.scheduled_lora,)),
        )


def test_phase27_scheduled_lora_context_owner_delegates_prepared_stale_context() -> (
    None
):
    """Scheduled-LoRA context owner should delegate without owning resolver work."""

    provider = _ScheduledContextProvider()
    current_context = _ScheduledCurrentContext()
    controller = PromptAutocompleteScheduledLoraContextController(
        context_provider=provider,
        enabled=True,
    )
    controller.bind_current_context(current_context)

    result = controller.trigger_word_suggestions(
        "mid",
        "mid",
        source_text="mid",
        source_identity=current_context.source_identity,
        query_identity=("tag", "mid"),
    )

    assert [suggestion.tag for suggestion in result.suggestions] == ["midna helmet"]
    assert provider.trigger_source_identity == current_context.source_identity
    assert provider.trigger_current_source_identity == current_context.source_identity
    assert provider.trigger_current_source_text is None
    assert current_context.refresh_calls == 1


def test_phase27_scheduled_lora_context_owner_fails_closed_when_disabled() -> None:
    """Disabled scheduled-LoRA context should not touch provider work."""

    provider = _ScheduledContextProvider()
    current_context = _ScheduledCurrentContext()
    controller = PromptAutocompleteScheduledLoraContextController(
        context_provider=provider,
        enabled=False,
    )
    controller.bind_current_context(current_context)

    result = controller.trigger_word_suggestions(
        "mid",
        "mid",
        source_text="mid",
        source_identity=current_context.source_identity,
        query_identity=("tag", "mid"),
    )

    assert result.suggestions == ()
    assert result.scheduled_lora_signature == ()
    assert provider.prewarm_calls == []
    assert provider.trigger_source_identity is None


def test_phase27_scheduled_lora_context_owner_fails_closed_before_binding() -> None:
    """Composition must not queue async work before a live context owner exists."""

    provider = _ScheduledContextProvider()
    controller = PromptAutocompleteScheduledLoraContextController(
        context_provider=provider,
        enabled=True,
    )

    result = controller.trigger_word_suggestions(
        "mid",
        "mid",
        source_text="mid",
        source_identity=None,
        query_identity=("tag", "mid"),
    )

    assert result.suggestions == ()
    assert result.scheduled_lora_signature == ()
    assert provider.prewarm_calls == []
    assert provider.trigger_source_identity is None


def test_phase27_scheduled_lora_context_owner_rejects_rebinding() -> None:
    """A composition error must not replace live async freshness authority."""

    controller = PromptAutocompleteScheduledLoraContextController(
        context_provider=_ScheduledContextProvider(),
        enabled=True,
    )
    controller.bind_current_context(_ScheduledCurrentContext())

    with pytest.raises(RuntimeError, match="already bound"):
        controller.bind_current_context(_ScheduledCurrentContext())
