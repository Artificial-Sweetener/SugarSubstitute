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

"""Compose editor-panel service bundles and optional preset sources."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLoraService,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)

from .composition_models import EditorPanelCompositionInputs
from .context.active_model_snapshot import PanelActiveModelSnapshotController
from .dimension_presets import EditorDimensionPresetCatalogSource
from .menus.node_input_preset_menu_source import EditorNodeInputPresetMenuSource
from .prompt.preset_adapter import PanelPromptSegmentPresetAdapter
from .service_bundle import (
    EditorPanelModelServiceBundle,
    EditorPanelPresetServiceBundle,
    EditorPanelPromptServiceBundle,
    EditorPanelServiceBundle,
)


@dataclass(frozen=True, slots=True)
class EditorPanelPresetSources:
    """Collect optional preset adapters that share active-model snapshots."""

    dimensions: EditorDimensionPresetCatalogSource | None
    node_inputs: EditorNodeInputPresetMenuSource | None
    prompt_segments: PanelPromptSegmentPresetAdapter | None


def compose_panel_services(
    inputs: EditorPanelCompositionInputs,
) -> EditorPanelServiceBundle:
    """Compose the immutable service graph consumed by panel features."""

    factories = inputs.execution_factories
    prompt = EditorPanelPromptServiceBundle(
        runtime=PromptEditorRuntimeServices(
            autocomplete_gateway=inputs.prompt_autocomplete_gateway,
            wildcard_catalog_gateway=inputs.prompt_wildcard_catalog_gateway,
            danbooru_url_import_service=inputs.danbooru_url_import_service,
            danbooru_wiki_service=inputs.danbooru_wiki_service,
            danbooru_image_preview_service=inputs.danbooru_image_preview_service,
            danbooru_recent_posts_service=inputs.danbooru_recent_posts_service,
            lora_catalog_service=inputs.prompt_lora_catalog_service,
            scheduled_lora_service=(
                inputs.prompt_scheduled_lora_service or PromptScheduledLoraService()
            ),
            spellcheck_service=inputs.prompt_spellcheck_service,
            thumbnail_asset_repository=inputs.thumbnail_asset_repository,
            model_metadata_action_handler=inputs.model_metadata_action_handler,
            prompt_task_executor_factory=(
                factories.prompt_task_executor_factory if factories else None
            ),
            danbooru_lookup_dispatcher_factory=(
                factories.danbooru_lookup_dispatcher_factory if factories else None
            ),
        ),
        scheduled_lora_provider=inputs.scheduled_lora_provider,
        feature_profile_service=inputs.prompt_feature_profile_service,
        model_picker_thumbnail_preload_route_factory=(
            factories.model_picker_thumbnail_preload_route_factory
            if factories
            else None
        ),
    )
    return EditorPanelServiceBundle(
        node_definition_gateway=inputs.node_definition_gateway,
        node_behavior_service=inputs.node_behavior_service,
        node_presentation_service=inputs.node_presentation_service,
        prompt=prompt,
        model=EditorPanelModelServiceBundle(
            catalog_service=inputs.model_catalog_service,
            choice_resolver=inputs.model_choice_resolver,
            thumbnail_asset_repository=inputs.thumbnail_asset_repository,
            model_metadata_action_handler=inputs.model_metadata_action_handler,
            empty_model_picker_action=inputs.empty_model_picker_action,
            model_updates=inputs.model_updates,
        ),
        presets=EditorPanelPresetServiceBundle(
            user_preset_service=inputs.user_preset_service,
        ),
    )


def compose_preset_sources(
    inputs: EditorPanelCompositionInputs,
    snapshots: PanelActiveModelSnapshotController,
) -> EditorPanelPresetSources:
    """Compose every preset adapter from the shared optional repository."""

    presets = inputs.user_preset_service
    if presets is None:
        return EditorPanelPresetSources(None, None, None)
    return EditorPanelPresetSources(
        dimensions=EditorDimensionPresetCatalogSource(
            user_preset_service=presets,
            active_model_snapshots=snapshots,
        ),
        node_inputs=EditorNodeInputPresetMenuSource(
            user_preset_service=presets,
            active_model_snapshots=snapshots,
        ),
        prompt_segments=PanelPromptSegmentPresetAdapter(
            user_preset_service=presets,
            active_model_snapshots=snapshots,
        ),
    )


__all__ = [
    "EditorPanelPresetSources",
    "compose_panel_services",
    "compose_preset_sources",
]
