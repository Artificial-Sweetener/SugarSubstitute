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

"""Build deterministic LoRA trigger-word menu actions for contract tests."""

from __future__ import annotations

from typing import Any, cast

from sugarsubstitute_shared.localization import app_text

from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureActionState,
    PromptFeatureCommandRequest,
    PromptFeatureSnapshotIdentity,
    PromptLoraTriggerWordsPayload,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptTriggerWordActionAdapter,
)


def trigger_words_action_for_lora(
    editor: PromptEditor,
    scheduled_lora: PromptScheduledLora,
    *,
    prompt_text: str,
) -> Any:
    """Build one trigger-word menu action against the editor's insertion owner."""

    insertion_text = (
        PromptScheduledLoraService().configured_trigger_words_for_insertion(
            scheduled_lora
        )
    )
    full_label = f"Trigger words: {scheduled_lora.display_name}"
    prepared_action = PromptFeatureActionState(
        action_id=f"lora.trigger_words:{scheduled_lora.backend_value}",
        label=full_label,
        ready=True,
        command_request=PromptFeatureCommandRequest(
            command_name="lora_insert_trigger_words",
            identity=PromptFeatureSnapshotIdentity(
                source_revision=editor.prompt_command_source_identity().source_revision
            ),
            payload=PromptLoraTriggerWordsPayload(
                insertion_text=insertion_text,
                display_name=scheduled_lora.display_name,
                full_label=app_text("Trigger words: %1", scheduled_lora.display_name),
            ),
        ),
    )
    return PromptTriggerWordActionAdapter(
        action_parent=editor,
        text_insertion_executor=cast(Any, editor)._context_insertion,
        identity_validator=lambda _identity: True,
    ).action_for_trigger_words(prepared_action)
