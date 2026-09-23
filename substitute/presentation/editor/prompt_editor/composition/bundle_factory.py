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

"""Assemble phase-local prompt-editor collaborators into the public bundle."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ..interactions import (
    PromptAutocompleteInputPort,
    PromptInlineLoraContextMenuPresenter,
)
from .collaborator_bundle import PromptEditorCollaborators
from .context import PromptEditorCompositionContext
from .feature_collaborators import (
    PromptEditorServiceCollaborators,
    PromptEditorSyntaxCollaborators,
)
from .projection_factory import PromptEditorProjectionCollaborators


def build_resize_handle(context: PromptEditorCompositionContext) -> QWidget:
    """Build the resize handle used by later signal and layout wiring."""
    return context.resize_handle_factory(context.editor)


def bundle_collaborators(
    projection: PromptEditorProjectionCollaborators,
    services: PromptEditorServiceCollaborators,
    autocomplete: PromptAutocompleteInputPort,
    syntax: PromptEditorSyntaxCollaborators,
    inline_lora_menu_presenter: PromptInlineLoraContextMenuPresenter,
    resize_handle: QWidget,
) -> PromptEditorCollaborators:
    """Combine phase-local construction results into the public bundle."""
    return PromptEditorCollaborators(
        lora_thumbnail_cache=projection.lora_thumbnail_cache,
        lora_thumbnail_preloader=projection.lora_thumbnail_preloader,
        surface=projection.surface,
        edit_execution=projection.edit_execution,
        shell_padding_fill_plane=projection.shell_padding_fill_plane,
        fill_plane=projection.fill_plane,
        lora_schedule_service=services.lora_schedule_service,
        prompt_scheduled_lora_service=services.prompt_scheduled_lora_service,
        scheduled_lora_resolver=services.scheduled_lora_resolver,
        scheduled_lora_context_provider=services.scheduled_lora_context_provider,
        feature_profile_controller=services.feature_profile_controller,
        scene_context_publication=services.scene_context_publication,
        scene_position_preparation=services.scene_position_preparation,
        search_feature_controller=services.search_feature_controller,
        wildcard_autocomplete_presentation=services.wildcard_autocomplete_presentation,
        wildcard_diagnostics_presentation=services.wildcard_diagnostics_presentation,
        segment_preset_controller=services.segment_preset_controller,
        danbooru_action_controller=services.danbooru_action_controller,
        autocomplete=autocomplete,
        document_service=syntax.document_service,
        mutation_service=syntax.mutation_service,
        syntax_profile=syntax.syntax_profile,
        syntax_service=syntax.syntax_service,
        token_weight_controls=syntax.token_weight_controls,
        weight_interaction=syntax.weight_interaction,
        wheel_controller=syntax.wheel_controller,
        syntax_renderer_coordinator=syntax.syntax_renderer_coordinator,
        interaction_controller=syntax.interaction_controller,
        inline_lora_menu_presenter=inline_lora_menu_presenter,
        resize_handle=resize_handle,
    )
