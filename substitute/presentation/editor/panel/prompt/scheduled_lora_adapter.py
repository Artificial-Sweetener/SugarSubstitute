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

"""Bind scheduled-LoRA providers to immutable prompt workflow contexts."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.prompt_editor.lora.effective_provider import (
    ScheduledLoraProvider,
    WorkflowPromptContext,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora


def build_scheduled_lora_resolver(
    *,
    provider: ScheduledLoraProvider | None,
    workflow_context: WorkflowPromptContext,
    cube_alias: str | None,
    prompt_node_name: str,
    prompt_field_key: str,
) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
    """Return a narrow resolver bound to one immutable prompt context."""

    if provider is None:
        return None

    def resolve(prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Resolve scheduled LoRAs for the supplied prompt text."""

        return provider.scheduled_loras_for_prompt_context(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            prompt_text=prompt_text,
        )

    setattr(resolve, "scheduled_lora_context_token", workflow_context.cache_token)
    return resolve


__all__ = ["build_scheduled_lora_resolver"]
