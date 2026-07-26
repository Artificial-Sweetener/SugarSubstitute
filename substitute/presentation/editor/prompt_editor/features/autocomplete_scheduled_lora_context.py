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

"""Prepare scheduled-LoRA trigger-word autocomplete context."""

from __future__ import annotations

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from collections.abc import Hashable
from typing import Protocol, cast

from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraContextProvider,
)

from .autocomplete_result_controller import (
    PromptAutocompleteResultSourceIdentity,
    PromptAutocompleteTriggerWordResult,
)


class PromptAutocompleteScheduledLoraCurrentContext(Protocol):
    """Describe current autocomplete context used for stale-safe publication."""

    def current_source_identity(self) -> PromptSourceIdentity | None:
        """Return the current source identity, if available."""

    def current_query_identity(self) -> Hashable | None:
        """Return the current prompt-safe tag query identity."""

    def refresh_current_query(self) -> None:
        """Refresh the current visible tag query after context publication."""


class PromptAutocompleteScheduledLoraContextController:
    """Provide trigger-word rows from prepared scheduled-LoRA context."""

    def __init__(
        self,
        *,
        context_provider: PromptScheduledLoraContextProvider | None,
        enabled: bool,
    ) -> None:
        """Store scheduled-LoRA collaborators before its current-context owner binds."""

        self._context_provider = context_provider
        self._current_context: PromptAutocompleteScheduledLoraCurrentContext | None = (
            None
        )
        self._enabled = enabled

    def bind_current_context(
        self,
        current_context: PromptAutocompleteScheduledLoraCurrentContext,
    ) -> None:
        """Bind the sole live context owner after composition resolves the cycle."""

        if self._current_context is not None:
            raise RuntimeError("Scheduled-LoRA current context is already bound.")
        self._current_context = current_context

    @property
    def enabled(self) -> bool:
        """Return whether scheduled-LoRA trigger rows may be requested."""

        return self._enabled and self._context_provider is not None

    def trigger_word_suggestions(
        self,
        prefix: str,
        prompt_text: str,
        *,
        source_text: str,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
        query_identity: Hashable | None,
    ) -> PromptAutocompleteTriggerWordResult:
        """Return cached trigger words and queue stale-safe refresh when cold."""

        provider = self._context_provider
        current_context = self._current_context
        if not self.enabled or provider is None or current_context is None:
            return PromptAutocompleteTriggerWordResult(
                suggestions=(),
                scheduled_lora_signature=(),
            )
        return cast(
            PromptAutocompleteTriggerWordResult,
            provider.trigger_word_result(
                prefix=prefix,
                prompt_text=prompt_text,
                source_text=source_text,
                source_identity=cast(
                    PromptSourceIdentity | None,
                    source_identity,
                ),
                query_identity=query_identity,
                current_source_text=None,
                current_source_identity=current_context.current_source_identity,
                current_query_identity=current_context.current_query_identity,
                refresh_current_query=current_context.refresh_current_query,
            ),
        )


__all__ = [
    "PromptAutocompleteScheduledLoraContextController",
    "PromptAutocompleteScheduledLoraCurrentContext",
]
