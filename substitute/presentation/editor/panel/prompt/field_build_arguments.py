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

"""Resolve prepared prompt inputs at the node-card field construction boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.application.node_behavior import FieldPresentation, ResolvedFieldSpec
from substitute.application.prompt_editor.conditioning import PromptConditioningContext
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.prompt.field_inputs import (
    NodeCardPromptFieldInputs,
)


@dataclass(frozen=True, slots=True)
class PromptFieldBuildArguments:
    """Carry prompt-only arguments resolved for the generic field pipeline."""

    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]] | None
    feature_profile: PromptEditorFeatureProfile | None
    syntax_profile: PromptSyntaxProfile | None
    conditioning_context: PromptConditioningContext | None


def prompt_field_build_arguments(
    field_spec: ResolvedFieldSpec,
    prompt_field_inputs: Mapping[str, NodeCardPromptFieldInputs] | None,
) -> PromptFieldBuildArguments:
    """Resolve one prompt field's prepared inputs without leaking into card assembly."""

    prepared = (
        prompt_field_inputs.get(field_spec.field_key)
        if field_spec.field_behavior.presentation == FieldPresentation.PROMPT_BOX
        and prompt_field_inputs is not None
        else None
    )
    profile = prepared.prompt_field_profile if prepared is not None else None
    return PromptFieldBuildArguments(
        scheduled_lora_resolver=(
            prepared.scheduled_lora_resolver if prepared is not None else None
        ),
        feature_profile=profile.feature_profile if profile is not None else None,
        syntax_profile=profile.syntax_profile if profile is not None else None,
        conditioning_context=(
            prepared.conditioning_context if prepared is not None else None
        ),
    )


__all__ = ["PromptFieldBuildArguments", "prompt_field_build_arguments"]
