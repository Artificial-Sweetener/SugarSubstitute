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

"""Define explicit service bundles consumed by editor-panel owners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.model_metadata import (
    ModelCatalogLookup,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.application.localization import NodePresentationService
from substitute.application.node_behavior import NodeBehaviorService
from substitute.application.ports import NodeDefinitionGateway
from substitute.application.prompt_editor import (
    PromptFeatureProfileService,
    PromptScheduledLora,
    ScheduledLoraProvider,
)
from substitute.application.user_presets import UserPresetService
from substitute.presentation.editor.panel.execution_factories import (
    DanbooruWikiLookupDispatcherFactory as DanbooruWikiLookupDispatcherFactory,
    EditorPanelExecutionFactories as EditorPanelExecutionFactories,
    ModelPickerThumbnailPreloadRouteFactory as ModelPickerThumbnailPreloadRouteFactory,
    PromptEditorTaskExecutorFactory as PromptEditorTaskExecutorFactory,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)


@dataclass(frozen=True, slots=True)
class EditorPanelPromptServiceBundle:
    """Group prompt-editor services injected into panel prompt field owners."""

    runtime: PromptEditorRuntimeServices
    scheduled_lora_provider: ScheduledLoraProvider | None = None
    feature_profile_service: PromptFeatureProfileService | None = None
    model_picker_thumbnail_preload_route_factory: (
        ModelPickerThumbnailPreloadRouteFactory | None
    ) = None


@dataclass(frozen=True, slots=True)
class EditorPanelModelServiceBundle:
    """Group model-choice services consumed by panel construction owners."""

    catalog_service: ModelCatalogLookup | None = None
    choice_resolver: RichChoiceResolver | None = None
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None


@dataclass(frozen=True, slots=True)
class EditorPanelPresetServiceBundle:
    """Group user-preset services used by panel menu-source owners."""

    user_preset_service: UserPresetService | None = None


@dataclass(frozen=True, slots=True)
class EditorPanelServiceBundle:
    """Collect application services behind one explicit panel boundary."""

    node_definition_gateway: NodeDefinitionGateway
    node_behavior_service: NodeBehaviorService
    node_presentation_service: NodePresentationService
    prompt: EditorPanelPromptServiceBundle
    model: EditorPanelModelServiceBundle
    presets: EditorPanelPresetServiceBundle


@dataclass(frozen=True, slots=True)
class EditorPanelFieldFactoryServices:
    """Carry factory-facing services prepared by panel construction owners."""

    prompt_services: EditorPanelPromptServiceBundle
    node_definition_gateway: NodeDefinitionGateway | None = None
    model_choice_snapshot_controller: object | None = None
    thumbnail_asset_repository: ThumbnailAssetRepository | None = None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None


@dataclass(frozen=True, slots=True)
class EditorPanelPromptFieldServices:
    """Carry services needed to instantiate a prompt editor field."""

    prompt_services: EditorPanelPromptServiceBundle
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]] | None
    model_metadata_action_handler: ModelMetadataContextActionHandler | None = None
    prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None
    danbooru_lookup_dispatcher_factory: DanbooruWikiLookupDispatcherFactory | None = (
        None
    )
    model_picker_thumbnail_preload_route_factory: (
        ModelPickerThumbnailPreloadRouteFactory | None
    ) = None
