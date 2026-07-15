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

"""Type surface for the canonical editor-panel view."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping, Sequence

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

from substitute.application.editor_search import EditorSearchResult
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    LiveNodeDefinitionError,
    NodeDisplayDecision,
    NodeBehaviorService,
    ResolvedFieldSpec,
)
from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueSource,
    WorkflowIssueState,
)
from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptFeatureProfileService,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSpellcheckService,
    PromptWheelAdjustmentMode,
    ScheduledLoraProvider,
    WorkflowPromptContext,
)
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ModelMetadataRefreshEvent,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.application.user_presets import UserPresetService
from substitute.presentation.errors import ErrorReportPresenterProtocol
from .context.active_model_context import PanelActiveModelContextController
from .context.active_model_snapshot import (
    PanelActiveModelSnapshotController,
)
from .menus.dimension_preset_menu_source import EditorDimensionPresetMenuSource
from .model_choice_snapshot_controller import PanelModelChoiceSnapshotController
from .projection_preparation import BehaviorRefreshReason
from .projection_session import EditorSurfaceProjectionSignature
from .prompt_profile_policy import PanelPromptFieldProfileDecision
from .service_bundle import EditorPanelExecutionFactories

class EditorPanel(QWidget):
    CUBE_SPACING: int
    currentCubeVisibleChanged: Any
    inputImageChanged: Any
    inputImageClicked: Any
    inputMaskChanged: Any
    inputMaskClicked: Any
    mainwindow: Any
    scheduled_lora_provider: ScheduledLoraProvider | None
    prompt_feature_profile_service: PromptFeatureProfileService | None
    model_choice_snapshot_controller: PanelModelChoiceSnapshotController
    active_model_context_controller: PanelActiveModelContextController
    active_model_snapshot_controller: PanelActiveModelSnapshotController
    dimension_preset_source: EditorDimensionPresetMenuSource | None
    _cube_states: Mapping[str, Any] | None
    _stack_order: list[str] | None
    _prompt_context_controller: Any

    def __init__(
        self,
        *,
        node_definition_gateway: NodeDefinitionGateway,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        node_behavior_service: NodeBehaviorService,
        danbooru_url_import_service: DanbooruUrlImportService | None = ...,
        danbooru_wiki_service: DanbooruWikiContentService | None = ...,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = ...,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = ...,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = ...,
        scheduled_lora_provider: ScheduledLoraProvider | None = ...,
        prompt_scheduled_lora_service: PromptScheduledLoraService | None = ...,
        prompt_spellcheck_service: PromptSpellcheckService | None = ...,
        prompt_feature_profile_service: PromptFeatureProfileService | None = ...,
        model_catalog_service: ModelCatalogLookup | None = ...,
        model_choice_resolver: RichChoiceResolver | None = ...,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = ...,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = ...,
        user_preset_service: UserPresetService | None = ...,
        error_presenter: ErrorReportPresenterProtocol | None = ...,
        workflow_issue_state: WorkflowIssueState | None = ...,
        workflow_id: str | None = ...,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = ...,
        editor_panel_execution_factories: EditorPanelExecutionFactories | None = ...,
    ) -> None: ...
    def clear_search_filters(self) -> None: ...
    def refresh_mask_picker(
        self,
        cube_alias: str,
        node_name: str,
        new_path: str,
    ) -> None: ...
    def refresh_model_metadata(self) -> None: ...
    def refresh_model_metadata_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int: ...
    def set_model_field_load_progress(
        self,
        *,
        cube_alias: str,
        node_name: str,
        field_key: str,
        percent: float | None,
        active: bool,
    ) -> None: ...
    def clear_model_field_load_progress(self) -> None: ...
    def mark_lora_metadata_dirty(self) -> None: ...
    def refresh_visible_lora_metadata(self) -> int: ...
    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None: ...
    def set_current_behavior_snapshot(
        self, snapshot: EditorBehaviorSnapshot | None
    ) -> None: ...
    def workflow_prompt_context(self) -> WorkflowPromptContext: ...
    def _prompt_workflow_context_for_feature_profiles(self) -> Any: ...
    def begin_projection_prompt_context(
        self,
        *,
        cube_states: Mapping[str, Any] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> None: ...
    def clear_projection_prompt_context(self, *, reason: str) -> None: ...
    def scheduled_lora_resolver_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None: ...
    def prompt_feature_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile | None: ...
    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision: ...
    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature: ...
    def is_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> bool: ...
    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None: ...
    def invalidate_projection(self, *, reason: str) -> None: ...
    def refresh_clean_projection(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None: ...
    def reorder_cube_widgets(self) -> None: ...
    def load_all_cubes(
        self,
        cube_entries: Sequence[tuple[str, Any]],
        cube_states: Mapping[str, Any] | None = ...,
        stack_order: Sequence[str] | None = ...,
        projection_signature: EditorSurfaceProjectionSignature | None = ...,
        on_complete: Callable[[], None] | None = ...,
    ) -> None: ...
    def insert_cube_section(
        self,
        cube_alias: str,
        cube_state: Any,
        cube_states: Mapping[str, Any] | None = ...,
        stack_order: Sequence[str] | None = ...,
        on_complete: Callable[[], None] | None = ...,
        completion_phase: str = ...,
    ) -> None: ...
    def rename_cube(self, old_key: str, new_key: str) -> None: ...
    def refresh_cube_header(self, alias: str) -> None: ...
    def remove_cube(self, route_key: str) -> None: ...
    def clear_layout(self) -> None: ...
    def has_pending_visible_projection_commit(self) -> bool: ...
    def finalize_pending_visible_projection(self) -> bool: ...
    def scroll_to_cube(
        self,
        cube_alias: str,
        animated: bool = ...,
        duration: int | None = ...,
        *,
        only_if_needed: bool = ...,
        on_finished: Callable[[], None] | None = ...,
    ) -> None: ...
    def reveal_loaded_cube(self, route_key: str) -> None: ...
    def reveal_new_cube(self, route_key: str) -> None: ...
    def reveal_cube_when_layout_ready(self, route_key: str) -> None: ...
    def handle_external_wheel(self, event: QWheelEvent) -> None: ...
    def scroll_to_input_widget(
        self,
        widget: QWidget,
        animated: bool = ...,
        duration: int | None = ...,
    ) -> None: ...
    def set_stack_order(self, stack_order: list[str]) -> None: ...
    def search_and_select(self, search_text: str, direction: str = ...) -> None: ...
    def focus_current_search_match(self) -> None: ...
    def build_search_corpus_snapshot(self) -> EditorBehaviorSnapshot | None: ...
    def highlight_inputs_matching(self, text: str) -> None: ...
    def apply_search_result(self, result: EditorSearchResult) -> None: ...
    def filter_node_cards_by_search(self, search_text: str) -> None: ...
    def randomize_all_seed_boxes(self) -> None: ...
    def configure_wheel_intent_for_widget(self, widget: QWidget) -> None: ...
    def build_node_card(
        self,
        node_name: str,
        inputs: dict[str, Any],
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: dict[str, Any],
        resolved_behavior: Any,
        display_decision: NodeDisplayDecision | None = ...,
        alias: str | None = ...,
        parent: Any | None = ...,
    ) -> Any: ...
    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None: ...
    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None: ...
    def sync_prompt_editor_values_from_buffers(self) -> None: ...
    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None: ...
    def update_all_hidden_fields(
        self,
        overrides: Any = ...,
        search_hidden_keys: set[Any] | None = ...,
    ) -> None: ...
    def set_hidden_field_keys(self, hidden_keys: set[Any]) -> None: ...
    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None: ...
    def sanitize_prompt_link_state(self) -> None: ...
    def reconcile_prompt_link_state(
        self,
        *,
        previous_cube_states: Mapping[str, object] | None,
        previous_stack_order: list[str] | None,
        cube_states: Mapping[str, object] | None,
        stack_order: list[str] | None,
    ) -> None: ...
    def refresh_link_widgets_for_cube(self, cube_alias: str) -> None: ...
    def refresh_node_behavior_state(
        self,
        search_hidden_keys: set[Any] | None = ...,
        override_hidden_field_keys: set[Any] | None = ...,
        node_search_text: str | None = ...,
        search_matching_nodes: set[tuple[str, str]] | None = ...,
        *,
        reason: BehaviorRefreshReason = ...,
        use_cached_snapshot: bool = ...,
    ) -> None: ...
    def hydrate_node_definitions_for_projection(self, *, reason: str) -> None: ...
    def begin_live_node_definition_report_projection(self) -> None: ...
    def register_projection_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        source: CubeRuntimeIssueSource,
    ) -> bool: ...
    def present_recoverable_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None: ...
    def clear_projection_runtime_issues(self) -> None: ...
    def set_cube_runtime_issues(
        self,
        cube_alias: str,
        issues: Sequence[CubeRuntimeIssue],
    ) -> None: ...
    def clear_cube_runtime_issues(self, cube_alias: str) -> None: ...
    def cube_runtime_issues(
        self,
        cube_alias: str,
    ) -> tuple[CubeRuntimeIssue, ...]: ...
    def cube_runtime_error_aliases(self) -> tuple[str, ...]: ...
    def refresh_projection_after_node_definition_update(
        self,
        *,
        refreshed_node_classes: Sequence[str],
    ) -> bool: ...
    def begin_behavior_refresh_transaction(self, *, reason: str) -> None: ...
    def end_behavior_refresh_transaction(self, *, reason: str) -> None: ...
    def invalidate_behavior_refresh_transaction(self, *, reason: str) -> None: ...
