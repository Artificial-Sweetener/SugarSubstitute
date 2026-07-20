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

"""Prepare LoRA context-menu actions without binding them to Qt widgets."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import app_text

from dataclasses import dataclass

from substitute.application.prompt_editor import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)

from ..commands import PromptFeatureCommandRequest, PromptFeatureSnapshotIdentity
from .catalog_snapshots import CatalogSnapshotIdentity
from .feature_profile_controller import (
    PromptFeatureActionState,
)


@dataclass(frozen=True, slots=True)
class PromptLoraTokenContext:
    """Describe one projected LoRA token using feature-owned value state."""

    prompt_name: str | None
    backend_value: str | None
    display_name: str
    trained_words: tuple[str, ...]
    model_page_url: str | None


@dataclass(frozen=True, slots=True)
class PromptLoraTriggerWordsPayload:
    """Carry trigger-word insertion text prepared for command execution."""

    insertion_text: str
    display_name: str
    full_label: ApplicationMessage
    snapshot_identity: CatalogSnapshotIdentity | None = None


@dataclass(frozen=True, slots=True)
class PromptLoraModelPagePayload:
    """Carry a model-page URL prepared for shell action presentation."""

    url: str
    snapshot_identity: CatalogSnapshotIdentity | None = None


PromptLoraTriggerWordsAction = PromptFeatureActionState[PromptLoraTriggerWordsPayload]
PromptLoraModelPageAction = PromptFeatureActionState[PromptLoraModelPagePayload]


class PromptLoraContextActionController:
    """Prepare LoRA model-page and trigger-word actions from cached metadata."""

    def __init__(
        self,
        *,
        scheduled_lora_service: PromptScheduledLoraService,
    ) -> None:
        """Store application services used for pure LoRA action preparation."""

        self._scheduled_lora_service = scheduled_lora_service

    def model_page_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
        *,
        identity: PromptFeatureSnapshotIdentity,
        snapshot_identity: CatalogSnapshotIdentity | None = None,
    ) -> PromptLoraModelPageAction | None:
        """Return a prepared model-page action for a projected LoRA token."""

        url = (
            ""
            if token_context.model_page_url is None
            else token_context.model_page_url.strip()
        )
        if not url:
            return None
        return PromptLoraModelPageAction(
            action_id="lora.open_model_page",
            label=app_text("Open CivitAI page"),
            ready=True,
            command_request=PromptFeatureCommandRequest(
                command_name="lora_open_model_page",
                identity=identity,
                payload=PromptLoraModelPagePayload(
                    url=url,
                    snapshot_identity=snapshot_identity,
                ),
            ),
        )

    def trigger_words_action_for_token(
        self,
        token_context: PromptLoraTokenContext,
        *,
        identity: PromptFeatureSnapshotIdentity,
        snapshot_identity: CatalogSnapshotIdentity | None = None,
    ) -> PromptLoraTriggerWordsAction | None:
        """Return a prepared trigger-word action for one inline LoRA token."""

        if not token_context.prompt_name or not token_context.backend_value:
            return None
        scheduled_lora = PromptScheduledLora(
            prompt_name=token_context.prompt_name,
            backend_value=token_context.backend_value,
            display_name=token_context.display_name,
            trained_words=token_context.trained_words,
            source="inline_prompt",
        )
        return self.trigger_words_action_for_lora(
            scheduled_lora,
            identity=identity,
            snapshot_identity=snapshot_identity,
        )

    def trigger_words_action_for_lora(
        self,
        scheduled_lora: PromptScheduledLora,
        *,
        identity: PromptFeatureSnapshotIdentity,
        snapshot_identity: CatalogSnapshotIdentity | None = None,
    ) -> PromptLoraTriggerWordsAction | None:
        """Return a prepared trigger-word action for one scheduled LoRA."""

        insertion_text = (
            self._scheduled_lora_service.configured_trigger_words_for_insertion(
                scheduled_lora
            )
        )
        if not insertion_text:
            return None
        full_label = self.trigger_words_full_label(scheduled_lora.display_name)
        return PromptLoraTriggerWordsAction(
            action_id=f"lora.trigger_words:{scheduled_lora.backend_value}",
            label=full_label,
            ready=True,
            command_request=PromptFeatureCommandRequest(
                command_name="lora_insert_trigger_words",
                identity=identity,
                payload=PromptLoraTriggerWordsPayload(
                    insertion_text=insertion_text,
                    display_name=scheduled_lora.display_name,
                    full_label=full_label,
                    snapshot_identity=snapshot_identity,
                ),
            ),
        )

    def loras_with_configured_trigger_words(
        self,
        scheduled_loras: tuple[PromptScheduledLora, ...],
    ) -> tuple[PromptScheduledLora, ...]:
        """Keep scheduled LoRAs that declare provider-authored trigger words."""

        return tuple(
            scheduled_lora
            for scheduled_lora in scheduled_loras
            if self._scheduled_lora_service.configured_trigger_words_for_insertion(
                scheduled_lora
            )
        )

    def trigger_words_full_label(self, display_name: str) -> ApplicationMessage:
        """Return the unelided action label for one trigger-word action."""

        return app_text("Trigger words: %1", display_name)


__all__ = [
    "PromptLoraContextActionController",
    "PromptLoraModelPageAction",
    "PromptLoraModelPagePayload",
    "PromptLoraTokenContext",
    "PromptLoraTriggerWordsAction",
    "PromptLoraTriggerWordsPayload",
]
