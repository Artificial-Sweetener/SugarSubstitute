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

"""Tests for prepared LoRA context-menu action policy."""

from __future__ import annotations

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.prompt_editor import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureSnapshotIdentity,
    PromptLoraContextActionController,
    PromptLoraTokenContext,
)


def test_lora_context_action_prepares_inline_trigger_word_payload() -> None:
    """Inline LoRA trigger-word actions should publish insertion payloads."""

    controller = PromptLoraContextActionController(
        scheduled_lora_service=PromptScheduledLoraService()
    )

    action = controller.trigger_words_action_for_token(
        PromptLoraTokenContext(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Friendly Midna",
            trained_words=("imp princess", "twili helmet"),
            model_page_url="https://civitai.example/models/1",
        ),
        identity=PromptFeatureSnapshotIdentity(source_revision=3),
    )

    assert action is not None
    assert action.command_request is not None
    assert action.command_request.command_name == "lora_insert_trigger_words"
    assert action.command_request.payload.insertion_text == (
        "imp princess, twili helmet"
    )
    assert (
        render_source_application_text(action.command_request.payload.full_label)
        == "Trigger words: Friendly Midna"
    )


def test_lora_context_action_filters_only_unconfigured_trigger_word_rows() -> None:
    """Every scheduled LoRA with configured words should reach menus."""

    controller = PromptLoraContextActionController(
        scheduled_lora_service=PromptScheduledLoraService()
    )
    ready_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    empty_lora = PromptScheduledLora(
        prompt_name="zelda",
        backend_value="zelda.safetensors",
        display_name="Zelda",
        trained_words=(),
        source="cube_field",
    )

    assert controller.loras_with_configured_trigger_words((ready_lora, empty_lora)) == (
        ready_lora,
    )
