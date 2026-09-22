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

"""Compose mounted catalog, trigger-word, and document feature facades."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..async_work import QtPromptEditorDebouncer, QtPromptEditorMainThreadDispatcher
from ..catalog_refresh_facade import (
    PromptEditorCatalogRefreshFacade,
    build_prompt_editor_catalog_refresh_facade,
)
from ..document_facade import (
    PromptEditorDocumentFacade,
    build_prompt_editor_document_facade,
)
from ..features import (
    PromptLoraMetadataIdentityPort,
    PromptLoraMetadataPresentation,
    PromptLoraTriggerWordController,
    PromptLoraTriggerWordHost,
)
from .collaborator_bundle import PromptEditorConstructionInputs
from .context import PromptEditorCompositionContext
from .core_runtime import PromptEditorCoreRuntime


@dataclass(frozen=True, slots=True)
class PromptEditorFeatureRuntimeBindings:
    """Declare host capabilities consumed by mounted feature presentation."""

    lora_metadata_identity: PromptLoraMetadataIdentityPort
    lora_trigger_word_host: PromptLoraTriggerWordHost
    is_visible: Callable[[], bool]
    update_host: Callable[[], None]


@dataclass(frozen=True, slots=True)
class PromptEditorFeatureRuntime:
    """Carry mounted catalog, trigger-word, and document feature owners."""

    lora_metadata: PromptLoraMetadataPresentation
    catalog_refresh: PromptEditorCatalogRefreshFacade
    lora_trigger_words: PromptLoraTriggerWordController
    document: PromptEditorDocumentFacade


def build_prompt_editor_feature_runtime(
    inputs: PromptEditorConstructionInputs,
    context: PromptEditorCompositionContext,
    core: PromptEditorCoreRuntime,
    bindings: PromptEditorFeatureRuntimeBindings,
) -> PromptEditorFeatureRuntime:
    """Compose feature presentation over one initialized core runtime."""

    services = core.services
    lora_metadata = PromptLoraMetadataPresentation(
        identity_port=bindings.lora_metadata_identity,
        feature_profile=services.feature_profile_controller,
        lora_catalog=inputs.prompt_lora_catalog_service,
        lora_schedule_service=services.lora_schedule_service,
        scheduled_lora_service=services.prompt_scheduled_lora_service,
        thumbnail_repository_available=inputs.thumbnail_asset_repository is not None,
    )
    catalog_refresh = build_prompt_editor_catalog_refresh_facade(
        is_visible=bindings.is_visible,
        interaction=core.syntax.interaction_controller,
        lora_presentation=lora_metadata,
        dispatcher=QtPromptEditorMainThreadDispatcher(context.editor),
        thumbnail_cache=core.projection.lora_thumbnail_cache,
        surface=core.projection.surface,
        segment_presets=services.segment_preset_controller,
        update_host=bindings.update_host,
    )
    lora_trigger_words = PromptLoraTriggerWordController(
        host=bindings.lora_trigger_word_host,
        scheduled_lora_service=services.prompt_scheduled_lora_service,
        scheduled_lora_context=services.scheduled_lora_context_provider,
        feature_profile_id=(
            lambda: services.feature_profile_controller.identity.feature_profile_id
        ),
        catalog_revision=lambda: lora_metadata.snapshot.catalog_revision,
        trigger_words_enabled=(
            lambda: services.feature_profile_controller.lora_trigger_words_enabled
        ),
        effective_prompts=services.scene_position_preparation.effective_prompt_texts,
        source_change_debouncer=QtPromptEditorDebouncer(
            interval_ms=(
                PromptLoraTriggerWordController.DEFAULT_SOURCE_SETTLE_DELAY_MS
            ),
            parent=context.editor,
        ),
    )
    document = build_prompt_editor_document_facade(
        inputs.prompt_document_semantics,
        core.projection.source_commands,
        core.syntax.interaction_controller,
        core.diagnostics,
        lora_trigger_words,
    )
    return PromptEditorFeatureRuntime(
        lora_metadata=lora_metadata,
        catalog_refresh=catalog_refresh,
        lora_trigger_words=lora_trigger_words,
        document=document,
    )


__all__ = [
    "PromptEditorFeatureRuntime",
    "PromptEditorFeatureRuntimeBindings",
    "build_prompt_editor_feature_runtime",
]
