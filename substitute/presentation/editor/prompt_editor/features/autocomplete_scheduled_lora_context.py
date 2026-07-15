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

from collections.abc import Hashable
from typing import Protocol, cast

from substitute.presentation.editor.prompt_editor.async_work.scheduled_lora_dispatcher import (
    PromptScheduledLoraContextProvider,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)

from .autocomplete_result_controller import (
    PromptAutocompleteResultSourceIdentity,
    PromptAutocompleteTriggerWordResult,
)


class PromptAutocompleteScheduledLoraCurrentContext(Protocol):
    """Describe current autocomplete context used for stale-safe publication."""

    def current_source_identity(self) -> PromptCommandSourceIdentity | None:
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
        current_context: PromptAutocompleteScheduledLoraCurrentContext,
        enabled: bool,
    ) -> None:
        """Store scheduled-LoRA collaborators without owning resolution."""

        self._context_provider = context_provider
        self._current_context = current_context
        self._enabled = enabled

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
        if not self.enabled or provider is None:
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
                    PromptCommandSourceIdentity | None,
                    source_identity,
                ),
                query_identity=query_identity,
                current_source_text=None,
                current_source_identity=self._current_context.current_source_identity,
                current_query_identity=self._current_context.current_query_identity,
                refresh_current_query=self._current_context.refresh_current_query,
            ),
        )


__all__ = [
    "PromptAutocompleteScheduledLoraContextController",
    "PromptAutocompleteScheduledLoraCurrentContext",
]
