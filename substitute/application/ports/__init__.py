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

"""Expose application-layer port contracts without eager facade imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.application.ports.appearance_preference_repository import (
        AppearancePreferenceRepository,
    )
    from substitute.application.ports.comfy_asset_stager import ComfyAssetStager
    from substitute.application.ports.comfy_gateway import (
        ComfyGateway,
        ComfyQueueMutationResult,
        ComfyQueueMutationStatus,
        ComfyQueueSnapshot,
        CubeExecutionTiming,
        GenerationExecutionTiming,
        GenerationVisualIdentity,
        InterruptResult,
        InterruptStatus,
        ListenerCallbacks,
        ListenerCompleted,
        ListenerFailure,
        ListenerHandle,
        ListenerOutputSource,
        ListenerSessionConnectRequest,
        ListenerSessionConnectResult,
        ListenerSessionHandle,
        ListenerStartRequest,
        ListenerStartResult,
        ModelLoadProgressUpdate,
        OutputImageUpdate,
        OutputSavePlan,
        PreviewImageUpdate,
        ProgressUpdate,
        QueuePromptResult,
        QueuePromptStatus,
        QueueVisualRunContext,
    )
    from substitute.application.ports.comfy_target_repository import (
        ComfyTargetConfigurationRepository,
    )
    from substitute.application.ports.cube_classification_cache import (
        CachedCubePickerClassification,
        CachedCubeSearchTerm,
        CubeClassificationCacheKey,
        CubeClassificationCacheRepository,
    )
    from substitute.application.ports.cube_icon_asset_fetcher import (
        CubeIconAsset,
        CubeIconAssetFetcher,
    )
    from substitute.application.ports.cube_icon_cache import (
        CubeIconCacheKey,
        RenderedCubeIconAsset,
        RenderedCubeIconCacheRepository,
    )
    from substitute.application.ports.cube_library_client import CubeLibraryClient
    from substitute.application.ports.cube_repository import (
        CachedCubeCatalogRepository,
        CubeCatalogRecord,
        CubeCatalogSnapshot,
        CubeDefinitionRecord,
        CubeRepository,
    )
    from substitute.application.ports.danbooru_cache_repository import (
        DanbooruCacheRepository,
    )
    from substitute.application.ports.danbooru_preference_repository import (
        DanbooruPreferenceRepository,
    )
    from substitute.application.ports.file_manager_gateway import (
        FileManagerGateway,
        FileRevealResult,
        FileRevealStatus,
    )
    from substitute.application.ports.generation_preview_preference_repository import (
        GenerationPreviewPreferenceRepository,
    )
    from substitute.application.ports.image_repository import ImageRepository
    from substitute.application.ports.installation_repository import (
        InstallationConfigurationRepository,
    )
    from substitute.application.ports.managed_runtime_repository import (
        ManagedRuntimeConfigurationRepository,
    )
    from substitute.application.ports.managed_runtime_selection_policy import (
        ManagedRuntimeSelectionPolicy,
    )
    from substitute.application.ports.node_definition_gateway import (
        NodeDefinitionGateway,
        NodeDefinitionHydrationResult,
        NodeDefinitionHydrator,
        NodeDefinitionRefreshEvent,
        NodeDefinitionRefreshObserver,
        ObservableNodeDefinitionGateway,
    )
    from substitute.application.ports.output_organization_preference_repository import (
        OutputOrganizationPreferenceRepository,
    )
    from substitute.application.ports.output_run_number_allocator import (
        OutputRunNumberAllocator,
    )
    from substitute.application.ports.prompt_autocomplete_gateway import (
        PromptAutocompleteGateway,
        PromptAutocompleteSuggestion,
    )
    from substitute.application.ports.prompt_editor_preference_repository import (
        PromptEditorPreferenceRepository,
    )
    from substitute.application.ports.prompt_tag_lexicon import (
        PromptTagLexicon,
        PromptTagLexiconSnapshot,
        PromptTagLexiconSnapshotProvider,
    )
    from substitute.application.ports.prompt_parenthesis_education_state import (
        PromptParenthesisEducationState,
    )
    from substitute.application.ports.prompt_wildcard_catalog_gateway import (
        PromptWildcardCatalogGateway,
        PromptWildcardReference,
        PromptWildcardResolution,
    )
    from substitute.application.ports.recipe_repository import (
        LoadedRecipeDocument,
        RecipeRepository,
        RecipeSourceKind,
        WorkflowRepository,
    )
    from substitute.application.ports.runtime_provisioner import RuntimeProvisioner
    from substitute.application.ports.runtime_repository import (
        RuntimeConfigurationRepository,
    )
    from substitute.application.ports.session_snapshot_repository import (
        SessionSnapshotRepository,
    )
    from substitute.application.ports.spellcheck_gateway import SpellCheckGateway
    from substitute.application.ports.workflow_payload_compiler import (
        WorkflowPayloadCompiler,
    )

_LAZY_EXPORTS = {
    "AppearancePreferenceRepository": (
        "substitute.application.ports.appearance_preference_repository"
    ),
    "CachedCubeCatalogRepository": "substitute.application.ports.cube_repository",
    "CachedCubePickerClassification": (
        "substitute.application.ports.cube_classification_cache"
    ),
    "CachedCubeSearchTerm": "substitute.application.ports.cube_classification_cache",
    "ComfyAssetStager": "substitute.application.ports.comfy_asset_stager",
    "ComfyGateway": "substitute.application.ports.comfy_gateway",
    "ComfyQueueMutationResult": "substitute.application.ports.comfy_gateway",
    "ComfyQueueMutationStatus": "substitute.application.ports.comfy_gateway",
    "ComfyQueueSnapshot": "substitute.application.ports.comfy_gateway",
    "ComfyTargetConfigurationRepository": (
        "substitute.application.ports.comfy_target_repository"
    ),
    "CubeCatalogRecord": "substitute.application.ports.cube_repository",
    "CubeCatalogSnapshot": "substitute.application.ports.cube_repository",
    "CubeClassificationCacheKey": (
        "substitute.application.ports.cube_classification_cache"
    ),
    "CubeClassificationCacheRepository": (
        "substitute.application.ports.cube_classification_cache"
    ),
    "CubeDefinitionRecord": "substitute.application.ports.cube_repository",
    "CubeExecutionTiming": "substitute.application.ports.comfy_gateway",
    "CubeIconAsset": "substitute.application.ports.cube_icon_asset_fetcher",
    "CubeIconAssetFetcher": "substitute.application.ports.cube_icon_asset_fetcher",
    "CubeIconCacheKey": "substitute.application.ports.cube_icon_cache",
    "CubeLibraryClient": "substitute.application.ports.cube_library_client",
    "CubeRepository": "substitute.application.ports.cube_repository",
    "DanbooruCacheRepository": "substitute.application.ports.danbooru_cache_repository",
    "DanbooruPreferenceRepository": (
        "substitute.application.ports.danbooru_preference_repository"
    ),
    "FileManagerGateway": "substitute.application.ports.file_manager_gateway",
    "FileRevealResult": "substitute.application.ports.file_manager_gateway",
    "FileRevealStatus": "substitute.application.ports.file_manager_gateway",
    "GenerationExecutionTiming": "substitute.application.ports.comfy_gateway",
    "GenerationPreviewPreferenceRepository": (
        "substitute.application.ports.generation_preview_preference_repository"
    ),
    "GenerationVisualIdentity": "substitute.application.ports.comfy_gateway",
    "ImageRepository": "substitute.application.ports.image_repository",
    "InstallationConfigurationRepository": (
        "substitute.application.ports.installation_repository"
    ),
    "InterruptResult": "substitute.application.ports.comfy_gateway",
    "InterruptStatus": "substitute.application.ports.comfy_gateway",
    "ListenerCallbacks": "substitute.application.ports.comfy_gateway",
    "ListenerCompleted": "substitute.application.ports.comfy_gateway",
    "ListenerFailure": "substitute.application.ports.comfy_gateway",
    "ListenerHandle": "substitute.application.ports.comfy_gateway",
    "ListenerOutputSource": "substitute.application.ports.comfy_gateway",
    "ListenerSessionConnectRequest": "substitute.application.ports.comfy_gateway",
    "ListenerSessionConnectResult": "substitute.application.ports.comfy_gateway",
    "ListenerSessionHandle": "substitute.application.ports.comfy_gateway",
    "ListenerStartRequest": "substitute.application.ports.comfy_gateway",
    "ListenerStartResult": "substitute.application.ports.comfy_gateway",
    "LoadedRecipeDocument": "substitute.application.ports.recipe_repository",
    "ManagedRuntimeConfigurationRepository": (
        "substitute.application.ports.managed_runtime_repository"
    ),
    "ManagedRuntimeSelectionPolicy": (
        "substitute.application.ports.managed_runtime_selection_policy"
    ),
    "ModelLoadProgressUpdate": "substitute.application.ports.comfy_gateway",
    "NodeDefinitionGateway": "substitute.application.ports.node_definition_gateway",
    "NodeDefinitionHydrationResult": (
        "substitute.application.ports.node_definition_gateway"
    ),
    "NodeDefinitionHydrator": "substitute.application.ports.node_definition_gateway",
    "NodeDefinitionRefreshEvent": (
        "substitute.application.ports.node_definition_gateway"
    ),
    "NodeDefinitionRefreshObserver": (
        "substitute.application.ports.node_definition_gateway"
    ),
    "ObservableNodeDefinitionGateway": (
        "substitute.application.ports.node_definition_gateway"
    ),
    "OutputImageUpdate": "substitute.application.ports.comfy_gateway",
    "OutputOrganizationPreferenceRepository": (
        "substitute.application.ports.output_organization_preference_repository"
    ),
    "OutputRunNumberAllocator": (
        "substitute.application.ports.output_run_number_allocator"
    ),
    "OutputSavePlan": "substitute.application.ports.comfy_gateway",
    "PreviewImageUpdate": "substitute.application.ports.comfy_gateway",
    "ProgressUpdate": "substitute.application.ports.comfy_gateway",
    "PromptAutocompleteGateway": (
        "substitute.application.ports.prompt_autocomplete_gateway"
    ),
    "PromptAutocompleteSuggestion": (
        "substitute.application.ports.prompt_autocomplete_gateway"
    ),
    "PromptEditorPreferenceRepository": (
        "substitute.application.ports.prompt_editor_preference_repository"
    ),
    "PromptTagLexicon": "substitute.application.ports.prompt_tag_lexicon",
    "PromptParenthesisEducationState": (
        "substitute.application.ports.prompt_parenthesis_education_state"
    ),
    "PromptTagLexiconSnapshot": "substitute.application.ports.prompt_tag_lexicon",
    "PromptTagLexiconSnapshotProvider": "substitute.application.ports.prompt_tag_lexicon",
    "PromptWildcardCatalogGateway": (
        "substitute.application.ports.prompt_wildcard_catalog_gateway"
    ),
    "PromptWildcardReference": (
        "substitute.application.ports.prompt_wildcard_catalog_gateway"
    ),
    "PromptWildcardResolution": (
        "substitute.application.ports.prompt_wildcard_catalog_gateway"
    ),
    "QueuePromptResult": "substitute.application.ports.comfy_gateway",
    "QueuePromptStatus": "substitute.application.ports.comfy_gateway",
    "QueueVisualRunContext": "substitute.application.ports.comfy_gateway",
    "RecipeRepository": "substitute.application.ports.recipe_repository",
    "RecipeSourceKind": "substitute.application.ports.recipe_repository",
    "RenderedCubeIconAsset": "substitute.application.ports.cube_icon_cache",
    "RenderedCubeIconCacheRepository": "substitute.application.ports.cube_icon_cache",
    "RuntimeConfigurationRepository": "substitute.application.ports.runtime_repository",
    "RuntimeProvisioner": "substitute.application.ports.runtime_provisioner",
    "SessionSnapshotRepository": (
        "substitute.application.ports.session_snapshot_repository"
    ),
    "SpellCheckGateway": "substitute.application.ports.spellcheck_gateway",
    "WorkflowPayloadCompiler": "substitute.application.ports.workflow_payload_compiler",
    "WorkflowRepository": "substitute.application.ports.recipe_repository",
}


def __getattr__(name: str) -> object:
    """Load one exported application port contract on first access."""

    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "CachedCubeCatalogRepository",
    "ComfyGateway",
    "ComfyQueueMutationResult",
    "ComfyQueueMutationStatus",
    "ComfyQueueSnapshot",
    "ComfyAssetStager",
    "ComfyTargetConfigurationRepository",
    "CubeExecutionTiming",
    "CubeCatalogRecord",
    "CubeCatalogSnapshot",
    "CachedCubePickerClassification",
    "CachedCubeSearchTerm",
    "CubeClassificationCacheKey",
    "CubeClassificationCacheRepository",
    "CubeDefinitionRecord",
    "CubeIconAsset",
    "CubeIconAssetFetcher",
    "CubeIconCacheKey",
    "CubeLibraryClient",
    "CubeRepository",
    "GenerationPreviewPreferenceRepository",
    "GenerationExecutionTiming",
    "GenerationVisualIdentity",
    "ImageRepository",
    "InstallationConfigurationRepository",
    "InterruptResult",
    "InterruptStatus",
    "LoadedRecipeDocument",
    "ManagedRuntimeConfigurationRepository",
    "ManagedRuntimeSelectionPolicy",
    "NodeDefinitionGateway",
    "NodeDefinitionHydrationResult",
    "NodeDefinitionHydrator",
    "NodeDefinitionRefreshEvent",
    "NodeDefinitionRefreshObserver",
    "ObservableNodeDefinitionGateway",
    "ListenerCallbacks",
    "ListenerCompleted",
    "ListenerFailure",
    "ListenerHandle",
    "ListenerOutputSource",
    "ListenerSessionConnectRequest",
    "ListenerSessionConnectResult",
    "ListenerSessionHandle",
    "ModelLoadProgressUpdate",
    "ListenerStartRequest",
    "ListenerStartResult",
    "OutputImageUpdate",
    "OutputOrganizationPreferenceRepository",
    "OutputRunNumberAllocator",
    "OutputSavePlan",
    "AppearancePreferenceRepository",
    "DanbooruCacheRepository",
    "DanbooruPreferenceRepository",
    "FileManagerGateway",
    "FileRevealResult",
    "FileRevealStatus",
    "PromptAutocompleteGateway",
    "PromptAutocompleteSuggestion",
    "PromptEditorPreferenceRepository",
    "PromptTagLexicon",
    "PromptParenthesisEducationState",
    "PromptTagLexiconSnapshot",
    "PromptTagLexiconSnapshotProvider",
    "PromptWildcardCatalogGateway",
    "PromptWildcardReference",
    "PromptWildcardResolution",
    "PreviewImageUpdate",
    "ProgressUpdate",
    "QueuePromptResult",
    "QueuePromptStatus",
    "QueueVisualRunContext",
    "RecipeRepository",
    "RecipeSourceKind",
    "RuntimeConfigurationRepository",
    "RuntimeProvisioner",
    "SessionSnapshotRepository",
    "RenderedCubeIconAsset",
    "RenderedCubeIconCacheRepository",
    "SpellCheckGateway",
    "WorkflowRepository",
    "WorkflowPayloadCompiler",
]
