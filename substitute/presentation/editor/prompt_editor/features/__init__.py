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

"""Expose prompt-editor feature controller foundation types."""

from ..commands import PromptFeatureCommandRequest, PromptFeatureSnapshotIdentity

from .catalog_snapshots import (
    PHASE23_CATALOG_FOREGROUND_INVENTORY,
    CatalogForegroundConsumer,
    CatalogForegroundPathInventoryItem,
    CatalogLookupClassification,
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from .diagnostic_menu_actions import (
    PromptContextMenuAction,
    PromptDiagnosticMenuActionEntry,
    PromptDiagnosticMenuActionSnapshot,
)
from .diagnostics_controller import (
    PromptDiagnosticsFeatureController,
    PromptDiagnosticsHost,
    PromptDiagnosticsSignalHost,
    PromptDiagnosticsSnapshot,
    PromptDiagnosticsSurface,
)
from .autocomplete_query_controller import (
    PromptAutocompleteQueryController,
    PromptAutocompleteQuerySourceSnapshot,
    PromptAutocompleteQueryState,
)
from .autocomplete_result_controller import (
    PromptAutocompleteLoraCatalogSnapshotProvider,
    PromptAutocompleteResultCacheKey,
    PromptAutocompleteResultController,
    PromptAutocompleteResultMode,
    PromptAutocompleteResultSnapshot,
    PromptAutocompleteResultSourceIdentity,
    PromptAutocompleteResultStatus,
    PromptAutocompleteSceneResultProvider,
    PromptScheduledLoraSignature,
    PromptAutocompleteTagContext,
    PromptAutocompleteTagResult,
    PromptAutocompleteTriggerWordProvider,
    PromptAutocompleteTriggerWordResult,
    PromptAutocompleteWildcardResultProvider,
)
from .autocomplete_scene_context import (
    PromptAutocompleteSceneContextController,
    PromptAutocompleteSceneContextProvider,
    PromptAutocompleteSceneContextSnapshot,
    PromptAutocompleteSceneContextSourceIdentity,
)
from .autocomplete_scheduled_lora_context import (
    PromptAutocompleteScheduledLoraContextController,
    PromptAutocompleteScheduledLoraCurrentContext,
)
from .context_menu_actions import (
    PromptContextMenuActionController,
)
from .context_menu_snapshot import (
    PromptContextMenuActionSnapshot,
    PromptContextMenuConcern,
    PromptContextMenuConcernReadiness,
    PromptContextMenuSnapshot,
    PromptContextMenuSnapshotController,
    PromptContextMenuSnapshotIdentity,
    PromptContextMenuSnapshotReadiness,
    PromptContextMenuSnapshotRequest,
)
from .danbooru_actions import (
    PromptDanbooruActionController,
    PromptDanbooruActionHost,
    PromptDanbooruActionSnapshot,
    PromptDanbooruDialogRunner,
    PromptDanbooruUrlImportState,
    PromptDanbooruWikiDialogRequest,
    PromptDanbooruWikiLookupPayload,
)
from .feature_profile_controller import (
    PromptFeatureActionState,
    PromptFeatureGateSnapshot,
    PromptFeatureProfileController,
    prompt_feature_profile_from_legacy_syntax,
    prompt_feature_profile_identity,
)
from .lora_action_snapshots import (
    PromptLoraActionSnapshot,
    PromptLoraTriggerWordProjector,
)
from .lora_context_menu import (
    PromptLoraContextActionController,
    PromptLoraModelPageAction,
    PromptLoraModelPagePayload,
    PromptLoraTokenContext,
    PromptLoraTriggerWordsAction,
    PromptLoraTriggerWordsPayload,
)
from .lora_metadata_controller import (
    PromptLoraMetadataFeatureController,
    PromptLoraMetadataHost,
    PromptLoraMetadataSnapshot,
)
from .lora_trigger_word_controller import (
    PromptLoraTriggerWordController,
    PromptLoraTriggerWordHost,
)
from .lora_picker_snapshots import (
    PromptLoraPickerRefreshCatalog,
    PromptLoraPickerRefreshResult,
    PromptLoraPickerSnapshot,
    PromptLoraPickerSnapshotController,
    PromptLoraPickerSnapshotIdentityProvider,
)
from .prompt_segment_preset_controller import PromptSegmentPresetController
from .prompt_segment_preset_models import (
    PromptSegmentPresetDialogResult,
    PromptSegmentPresetDialogRunner,
    PromptSegmentPresetMenuItem,
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetMenuSection,
    PromptSegmentPresetSaveDialogRequest,
    PromptSegmentPresetSaveState,
    PromptSegmentPresetSnapshot,
    PromptSegmentPresetSource,
    PromptSegmentPresetSourceSnapshot,
)
from .prompt_segment_preset_source import EditorPromptSegmentPresetMenuSource
from .prompt_segment_selection import (
    PromptSegmentContextInsertState,
    PromptSegmentPresetHost,
    PromptSegmentSelectionSnapshot,
    PromptSegmentTextInsertionExecutor,
)
from .paste_import_controller import (
    PromptDanbooruPasteImportController,
    PromptDanbooruSourceReplacementExecutor,
)
from .scene_controller import (
    PromptSceneAutocompleteState,
    PromptSceneContextSnapshot,
    PromptSceneFeatureController,
    PromptScenePositionContext,
    PromptScenePositionContextSnapshot,
    PromptSceneQueueActionState,
    PromptSceneSourceHost,
)
from .search_controller import (
    PromptSearchFeatureController,
    PromptSearchHighlightSnapshot,
    PromptSearchHighlightState,
    PromptSearchProjectionSurface,
    PromptSearchSourceHost,
)
from .wildcard_controller import (
    PromptWildcardAutocompleteCacheKey,
    PromptWildcardAutocompleteQuerySnapshot,
    PromptWildcardAutocompleteRefreshCallback,
    PromptWildcardAutocompleteRequest,
    PromptWildcardAutocompleteState,
    PromptWildcardContextAction,
    PromptWildcardDiagnosticsState,
    PromptWildcardFeatureController,
    PromptWildcardNumericStepState,
    PromptWildcardPresentationSnapshot,
    PromptWildcardSourceHost,
)

__all__ = [
    "PromptContextMenuActionController",
    "PromptContextMenuAction",
    "PromptContextMenuActionSnapshot",
    "PromptContextMenuConcern",
    "PromptContextMenuConcernReadiness",
    "PromptContextMenuSnapshot",
    "PromptContextMenuSnapshotController",
    "PromptContextMenuSnapshotIdentity",
    "PromptContextMenuSnapshotReadiness",
    "PromptContextMenuSnapshotRequest",
    "CatalogForegroundConsumer",
    "CatalogForegroundPathInventoryItem",
    "CatalogLookupClassification",
    "CatalogSnapshotIdentity",
    "CatalogSnapshotReadiness",
    "CatalogSnapshotStatus",
    "PHASE23_CATALOG_FOREGROUND_INVENTORY",
    "PromptAutocompleteLoraCatalogSnapshotProvider",
    "PromptAutocompleteQueryController",
    "PromptAutocompleteQuerySourceSnapshot",
    "PromptAutocompleteQueryState",
    "PromptAutocompleteResultCacheKey",
    "PromptAutocompleteResultController",
    "PromptAutocompleteResultMode",
    "PromptAutocompleteResultSnapshot",
    "PromptAutocompleteResultSourceIdentity",
    "PromptAutocompleteResultStatus",
    "PromptAutocompleteSceneResultProvider",
    "PromptScheduledLoraSignature",
    "PromptAutocompleteSceneContextController",
    "PromptAutocompleteSceneContextProvider",
    "PromptAutocompleteSceneContextSnapshot",
    "PromptAutocompleteSceneContextSourceIdentity",
    "PromptAutocompleteScheduledLoraContextController",
    "PromptAutocompleteScheduledLoraCurrentContext",
    "PromptAutocompleteTagContext",
    "PromptAutocompleteTagResult",
    "PromptAutocompleteTriggerWordProvider",
    "PromptAutocompleteTriggerWordResult",
    "PromptAutocompleteWildcardResultProvider",
    "PromptDanbooruActionController",
    "PromptDanbooruActionHost",
    "PromptDanbooruActionSnapshot",
    "PromptDanbooruDialogRunner",
    "PromptDanbooruPasteImportController",
    "PromptDanbooruSourceReplacementExecutor",
    "PromptDanbooruUrlImportState",
    "PromptDanbooruWikiDialogRequest",
    "PromptDanbooruWikiLookupPayload",
    "PromptDiagnosticsFeatureController",
    "PromptDiagnosticMenuActionEntry",
    "PromptDiagnosticMenuActionSnapshot",
    "PromptDiagnosticsHost",
    "PromptDiagnosticsSignalHost",
    "PromptDiagnosticsSnapshot",
    "PromptDiagnosticsSurface",
    "PromptFeatureActionState",
    "PromptFeatureCommandRequest",
    "PromptFeatureGateSnapshot",
    "PromptFeatureProfileController",
    "PromptFeatureSnapshotIdentity",
    "PromptLoraContextActionController",
    "PromptLoraTriggerWordProjector",
    "PromptLoraActionSnapshot",
    "PromptLoraMetadataFeatureController",
    "PromptLoraMetadataHost",
    "PromptLoraMetadataSnapshot",
    "PromptLoraTriggerWordController",
    "PromptLoraTriggerWordHost",
    "PromptLoraPickerRefreshCatalog",
    "PromptLoraPickerRefreshResult",
    "PromptLoraPickerSnapshot",
    "PromptLoraPickerSnapshotController",
    "PromptLoraPickerSnapshotIdentityProvider",
    "PromptLoraModelPageAction",
    "PromptLoraModelPagePayload",
    "PromptLoraTokenContext",
    "PromptLoraTriggerWordsAction",
    "PromptLoraTriggerWordsPayload",
    "EditorPromptSegmentPresetMenuSource",
    "PromptSegmentContextInsertState",
    "PromptSegmentPresetController",
    "PromptSegmentPresetDialogResult",
    "PromptSegmentPresetDialogRunner",
    "PromptSegmentPresetHost",
    "PromptSegmentPresetMenuItem",
    "PromptSegmentPresetMenuModel",
    "PromptSegmentPresetMenuSection",
    "PromptSegmentPresetSaveDialogRequest",
    "PromptSegmentPresetSaveState",
    "PromptSegmentPresetSnapshot",
    "PromptSegmentPresetSource",
    "PromptSegmentPresetSourceSnapshot",
    "PromptSegmentSelectionSnapshot",
    "PromptSegmentTextInsertionExecutor",
    "PromptSceneAutocompleteState",
    "PromptSceneContextSnapshot",
    "PromptSceneFeatureController",
    "PromptScenePositionContext",
    "PromptScenePositionContextSnapshot",
    "PromptSceneQueueActionState",
    "PromptSceneSourceHost",
    "PromptSearchFeatureController",
    "PromptSearchHighlightSnapshot",
    "PromptSearchHighlightState",
    "PromptSearchProjectionSurface",
    "PromptSearchSourceHost",
    "PromptWildcardAutocompleteState",
    "PromptWildcardAutocompleteCacheKey",
    "PromptWildcardAutocompleteQuerySnapshot",
    "PromptWildcardAutocompleteRefreshCallback",
    "PromptWildcardAutocompleteRequest",
    "PromptWildcardContextAction",
    "PromptWildcardDiagnosticsState",
    "PromptWildcardFeatureController",
    "PromptWildcardNumericStepState",
    "PromptWildcardPresentationSnapshot",
    "PromptWildcardSourceHost",
    "prompt_feature_profile_from_legacy_syntax",
    "prompt_feature_profile_identity",
]
