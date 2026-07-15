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

"""Own scheduled-LoRA context lifecycle and trigger-word action projection."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Protocol

from substitute.application.prompt_editor import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)

from ..async_work import PromptScheduledLoraContextProvider
from ..commands import PromptCommandSourceIdentity, PromptFeatureSnapshotIdentity
from .lora_action_snapshots import (
    PromptLoraActionSnapshot,
    PromptLoraTriggerWordProjector,
)
from .lora_context_menu import (
    PromptLoraContextActionController,
    PromptLoraTokenContext,
    PromptLoraTriggerWordsAction,
)


class PromptLoraTriggerWordHost(Protocol):
    """Describe source state required by the trigger-word owner."""

    def toPlainText(self) -> str:
        """Return the current raw prompt source."""

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity | None:
        """Return the current prompt command identity."""


class PromptLoraTriggerWordController:
    """Coordinate one authoritative LoRA context and action projection boundary."""

    def __init__(
        self,
        *,
        host: PromptLoraTriggerWordHost,
        scheduled_lora_service: PromptScheduledLoraService,
        scheduled_lora_context: PromptScheduledLoraContextProvider | None,
        feature_profile_id: Callable[[], Hashable | None],
        catalog_revision: Callable[[], Hashable | None],
        trigger_words_enabled: Callable[[], bool],
        effective_prompts: Callable[[], tuple[str, ...]],
    ) -> None:
        """Store lifecycle, identity, and pure projection collaborators."""

        self._host = host
        self._scheduled_lora_context = scheduled_lora_context
        self._feature_profile_id = feature_profile_id
        self._catalog_revision = catalog_revision
        self._effective_prompts = effective_prompts
        self._projector = PromptLoraTriggerWordProjector(
            context_actions=PromptLoraContextActionController(
                scheduled_lora_service=scheduled_lora_service,
            ),
            source_identity_provider=host.prompt_command_source_identity,
            feature_profile_id_provider=feature_profile_id,
            catalog_revision_provider=catalog_revision,
            trigger_words_enabled=trigger_words_enabled,
        )

    def handle_source_changed(self) -> None:
        """Warm authoritative scheduled-LoRA context after every source commit."""

        self.prewarm_current_source()

    def prewarm_current_source(self) -> bool:
        """Request context preparation for the current raw prompt source."""

        requested = False
        prompt_texts = dict.fromkeys(
            (self._host.toPlainText(), *self._effective_prompts())
        )
        for prompt_text in prompt_texts:
            requested = self.prewarm_prompt(prompt_text) or requested
        return requested

    def prewarm_prompt(self, prompt_text: str) -> bool:
        """Request context preparation for one raw or effective prompt."""

        context = self._scheduled_lora_context
        return False if context is None else context.prewarm(prompt_text)

    def snapshot_for_prompt(self, *, prompt_text: str) -> PromptLoraActionSnapshot:
        """Project trigger actions from the authoritative context snapshot."""

        context = self._scheduled_lora_context
        cached_context = (
            None if context is None else context.cached_context_snapshot(prompt_text)
        )
        if cached_context is None:
            self.prewarm_prompt(prompt_text)
        return self._projector.snapshot_for_prompt(
            prompt_text=prompt_text,
            cached_context=cached_context,
        )

    def unavailable_snapshot(
        self,
        *,
        unavailable_reason: str,
    ) -> PromptLoraActionSnapshot:
        """Return an unavailable snapshot for an invalid scene context."""

        if not unavailable_reason.strip():
            raise ValueError("unavailable_reason must not be blank.")
        return self._projector.unavailable_snapshot_for_prompt(
            prompt_text="",
            unavailable_reason=unavailable_reason,
        )

    def inline_action(
        self,
        token_context: PromptLoraTokenContext,
        *,
        prompt_text: str,
    ) -> PromptLoraTriggerWordsAction | None:
        """Project one inline trigger action from token-owned metadata."""

        return self._projector.trigger_words_action_for_token(
            token_context,
            prompt_text=prompt_text,
        )

    def cached_scheduled_loras(
        self,
        prompt_text: str,
    ) -> tuple[PromptScheduledLora, ...] | None:
        """Return scheduled LoRAs from the single authoritative context owner."""

        context = self._scheduled_lora_context
        if context is None:
            return None
        return context.cached_scheduled_loras(prompt_text)

    def action_identity_is_current(
        self,
        identity: PromptFeatureSnapshotIdentity,
    ) -> bool:
        """Reject actions prepared against stale source, profile, or catalog state."""

        source_identity = self._host.prompt_command_source_identity()
        if identity.stale or source_identity is None:
            return False
        if identity.source_revision != source_identity.source_revision:
            return False
        if identity.feature_profile_id != self._feature_profile_id():
            return False
        return identity.catalog_revision == self._catalog_revision()


__all__ = [
    "PromptLoraTriggerWordController",
    "PromptLoraTriggerWordHost",
]
