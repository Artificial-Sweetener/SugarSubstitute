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

"""Render and coordinate the editor-panel view for workflow cube stacks."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping as MappingABC, Sequence
from typing import Mapping

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid as _qt_is_valid

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    NodeBehaviorService,
    ResolvedFieldSpec,
)
from substitute.application.localization import NodePresentationService
from substitute.application.editor_search import EditorSearchResult
from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.workflows import (
    NodeLinkIdentity,
    WorkflowIssueState,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogLookup,
)
from substitute.application.prompt_editor.diagnostics.spellcheck import (
    PromptSpellcheckService,
)
from substitute.application.prompt_editor.features.profile import (
    PromptFeatureProfileService,
)
from substitute.application.prompt_editor.lora.effective_provider import (
    ScheduledLoraProvider,
    WorkflowPromptContext,
)
from substitute.application.prompt_editor.lora.scheduled import (
    PromptScheduledLora,
    PromptScheduledLoraService,
)
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.application.model_metadata import (
    ModelCatalogLookup,
    ModelMetadataRefreshEvent,
    RichChoiceResolver,
    ThumbnailAssetRepository,
)
from substitute.application.model_metadata.ultralytics_thumbnail_associations import (
    UltralyticsThumbnailAssociationService,
)
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataContextActionHandler,
)
from substitute.presentation.model_discovery import EmptyModelPickerAction
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.application.user_presets import UserPresetService
from substitute.application.overrides import SamplerSchedulerLinkStateService
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_warning,
)
from .composition import compose_editor_panel
from .composition_models import EditorPanelCompositionInputs
from .cube_registry import EditorCubeRegistry
from .prompt.profile_policy import PanelPromptFieldProfileDecision
from .runtime_access import (
    cube_registry_for_panel as _cube_registry_for_panel,
    cube_reveal_controller_for_panel as _cube_reveal_controller_for_panel,
    cube_visibility_menu_controller_for_panel as _cube_visibility_menu_controller_for_panel,
    current_behavior_snapshot_for_panel as _current_behavior_snapshot_for_panel,
    field_state_controller_for_panel as _field_state_controller_for_panel,
    field_sync_controller_for_panel as _field_sync_controller_for_panel,
    lora_metadata_refresh_controller_for_panel as _lora_metadata_refresh_controller_for_panel,
    projection_coordinator_for_panel as _projection_coordinator_for_panel,
    projection_stack_order as _projection_stack_order,
    search_controller_for_panel as _search_controller_for_panel,
)
from .service_bundle import (
    EditorPanelExecutionFactories,
)
from .behavior.panel_ports import behavior_applier_for_panel
from .projection_preparation import BehaviorRefreshReason
from .projection_surface_state import EditorSurfaceProjectionSignature
from .factories.meta_factories import (
    sanitize_sampler_link_selection,
    sanitize_scheduler_link_selection,
)
from .node_card.body_contribution import NodeCardBodyContributor
from .node_card_builder import NodeCardBuilder
from .node_definition_runtime import EditorPanelNodeDefinitionRuntime
from .prompt.field_inputs import build_node_card_prompt_field_inputs
from .prompt_interaction import EditorPanelPromptInteraction
from .widgets.cube_section_builder import cube_section_builder_for_panel

_LOGGER = get_logger("presentation.editor.panel.view")


def isValid(obj: object) -> bool:  # noqa: N802
    """Return whether one Qt wrapper is valid for panel test hooks."""

    return bool(_qt_is_valid(obj))


_BEHAVIOR_TRANSACTION_INVALIDATING_REASONS: frozenset[BehaviorRefreshReason] = (
    frozenset(
        {
            "cube_removed",
            "cube_renamed",
            "stack_reordered",
            "search_changed",
            "node_activation_changed",
            "node_link_changed",
            "prompt_link_changed",
            "node_definition_changed",
            "model_options_changed",
        }
    )
)
_PROJECTION_INVALIDATING_REASONS: frozenset[BehaviorRefreshReason] = frozenset(
    reason
    for reason in _BEHAVIOR_TRANSACTION_INVALIDATING_REASONS
    if reason != "model_options_changed"
)


class EditorPanel(
    EditorPanelPromptInteraction,
    EditorPanelNodeDefinitionRuntime,
    QWidget,
):
    """Render one workflow editor surface and coordinate cube-section refreshes."""

    CUBE_SPACING = EDITOR_SECTION_GAP
    currentCubeVisibleChanged = Signal(str)
    inputImageChanged = Signal(str, str, str)
    inputImageClicked = Signal(str, str, str)
    inputMaskChanged = Signal(str, str, str)
    inputMaskClicked = Signal(str, str, str)
    inputMaskOpacityChanged = Signal(str, str, float)
    inputMaskOpacityCommitted = Signal(str, str, float, float)
    promptEditorLayoutChanged = Signal()
    promptSceneQueueRequested = Signal(str)

    def resizeEvent(self, event):
        """Forward resize events to the base widget implementation."""

        super().resizeEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Cancel automated cube reveal when the user scrolls the editor."""

        if self._is_user_scroll_interruption(watched, event):
            self._cancel_active_cube_reveal_scroll()
        return super().eventFilter(watched, event)

    def _is_user_scroll_interruption(self, watched: QObject, event: QEvent) -> bool:
        """Return whether one viewport event should cancel automated cube reveal."""

        event_type = event.type()
        interruption_type = None
        if event_type == QEvent.Type.Wheel:
            interruption_type = "wheel"
        elif event_type == QEvent.Type.MouseButtonPress:
            interruption_type = "mouse_press"
        return _cube_reveal_controller_for_panel(self).is_user_scroll_interruption(
            watched,
            interruption_type,
        )

    def _cancel_active_cube_reveal_scroll(self) -> None:
        """Stop active or pending cube reveal motion after deliberate user input."""

        _cube_reveal_controller_for_panel(self).cancel_active_cube_reveal_scroll()

    def refresh_mask_picker(self, cube_alias: str, node_name: str, new_path: str):
        """Refresh the mask picker matching one cube and node identity."""

        self.field_presentation.refresh_mask_picker(cube_alias, node_name, new_path)

    def refresh_model_metadata(self) -> None:
        """Refresh every model picker widget from current metadata."""

        self.field_presentation.refresh_model_metadata()

    def refresh_model_metadata_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Refresh visible model picker state affected by one metadata event."""

        return self.field_presentation.refresh_model_metadata_for_event(event)

    def clear_model_thumbnail_caches_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Clear affected model picker thumbnail caches after image asset updates."""

        return self.field_presentation.clear_model_thumbnail_caches_for_event(event)

    def clear_lora_thumbnail_caches(self) -> int:
        """Clear prompt-editor LoRA thumbnail caches owned by this panel."""

        return self.field_presentation.clear_lora_thumbnail_caches()

    def set_model_field_load_progress(
        self,
        *,
        cube_alias: str,
        node_name: str,
        field_key: str,
        percent: float | None,
        active: bool,
    ) -> None:
        """Route source-enriched model-load progress to one model picker field."""

        self.field_presentation.set_model_field_load_progress(
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            percent=percent,
            active=active,
        )

    def clear_model_field_load_progress(self) -> None:
        """Clear model-load progress from all tracked model picker fields."""

        self.field_presentation.clear_model_field_load_progress()

    def mark_lora_metadata_dirty(self) -> None:
        """Mark prompt editor LoRA metadata dirty without rebuilding projections."""

        _lora_metadata_refresh_controller_for_panel(self).mark_lora_metadata_dirty()

    def refresh_visible_lora_metadata(self) -> int:
        """Refresh dirty visible prompt editors that need LoRA metadata."""

        return _lora_metadata_refresh_controller_for_panel(
            self
        ).refresh_visible_lora_metadata()

    def __init__(
        self,
        *,
        node_definition_gateway: NodeDefinitionGateway,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        node_behavior_service: NodeBehaviorService,
        node_presentation_service: NodePresentationService,
        danbooru_url_import_service: DanbooruUrlImportService | None = None,
        danbooru_wiki_service: DanbooruWikiContentService | None = None,
        danbooru_image_preview_service: DanbooruImagePreviewService | None = None,
        danbooru_recent_posts_service: DanbooruRecentPostsService | None = None,
        prompt_lora_catalog_service: PromptLoraCatalogLookup | None = None,
        scheduled_lora_provider: ScheduledLoraProvider | None = None,
        prompt_scheduled_lora_service: PromptScheduledLoraService | None = None,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        prompt_feature_profile_service: PromptFeatureProfileService | None = None,
        model_catalog_service: ModelCatalogLookup | None = None,
        model_choice_resolver: RichChoiceResolver | None = None,
        thumbnail_asset_repository: ThumbnailAssetRepository | None = None,
        model_metadata_action_handler: ModelMetadataContextActionHandler | None = None,
        ultralytics_thumbnail_associations: (
            UltralyticsThumbnailAssociationService | None
        ) = None,
        empty_model_picker_action: EmptyModelPickerAction | None = None,
        model_updates: ModelUpdatePickerBridge | None = None,
        user_preset_service: UserPresetService | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        workflow_issue_state: WorkflowIssueState | None = None,
        workflow_id: str | None = None,
        editor_panel_execution_factories: EditorPanelExecutionFactories | None = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        node_card_body_contributors: tuple[NodeCardBodyContributor, ...] = (),
    ) -> None:
        """Initialize the passive view and delegate runtime composition."""

        super().__init__()
        compose_editor_panel(
            self,
            EditorPanelCompositionInputs(
                node_definition_gateway=node_definition_gateway,
                prompt_autocomplete_gateway=prompt_autocomplete_gateway,
                prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
                node_behavior_service=node_behavior_service,
                node_presentation_service=node_presentation_service,
                danbooru_url_import_service=danbooru_url_import_service,
                danbooru_wiki_service=danbooru_wiki_service,
                danbooru_image_preview_service=danbooru_image_preview_service,
                danbooru_recent_posts_service=danbooru_recent_posts_service,
                prompt_lora_catalog_service=prompt_lora_catalog_service,
                scheduled_lora_provider=scheduled_lora_provider,
                prompt_scheduled_lora_service=prompt_scheduled_lora_service,
                prompt_spellcheck_service=prompt_spellcheck_service,
                prompt_feature_profile_service=prompt_feature_profile_service,
                model_catalog_service=model_catalog_service,
                model_choice_resolver=model_choice_resolver,
                thumbnail_asset_repository=thumbnail_asset_repository,
                model_metadata_action_handler=model_metadata_action_handler,
                ultralytics_thumbnail_associations=(ultralytics_thumbnail_associations),
                empty_model_picker_action=empty_model_picker_action,
                model_updates=model_updates,
                user_preset_service=user_preset_service,
                error_presenter=error_presenter,
                workflow_issue_state=workflow_issue_state,
                workflow_id=workflow_id,
                execution_factories=editor_panel_execution_factories,
                wheel_adjustment_mode=wheel_adjustment_mode,
                node_card_body_contributors=node_card_body_contributors,
            ),
        )

    def set_cube_stack_unavailable_progress(self, progress: float) -> None:
        """Apply the shared stack-transition progress to editor content spacing."""

        self._content_gutter_controller.apply_cube_stack_unavailable_progress(progress)

    def content_horizontal_gutters(self) -> tuple[int, int]:
        """Return live editor content gutters for shell geometry diagnostics."""

        return self._content_gutter_controller.horizontal_gutters()

    @property
    def node_definition_gateway(self) -> NodeDefinitionGateway:
        """Return the host-facing node-definition gateway."""

        return self._services.node_definition_gateway

    @property
    def node_behavior_service(self) -> NodeBehaviorService:
        """Return the host-facing node-behavior service."""

        return self._services.node_behavior_service

    @property
    def prompt_scheduled_lora_service(self) -> PromptScheduledLoraService:
        """Return the scheduled-LoRA service used by prompt field owners."""

        return self._services.prompt.runtime.scheduled_lora_service_or_default()

    @property
    def scheduled_lora_provider(self) -> ScheduledLoraProvider | None:
        """Return the optional scheduled-LoRA provider for prompt contexts."""

        return self._services.prompt.scheduled_lora_provider

    @property
    def prompt_spellcheck_service(self) -> PromptSpellcheckService | None:
        """Return the optional prompt spellcheck service for host integrations."""

        return self._services.prompt.runtime.spellcheck_service

    @property
    def prompt_feature_profile_service(self) -> PromptFeatureProfileService | None:
        """Return the optional prompt feature-profile service for prompt contexts."""

        return self._services.prompt.feature_profile_service

    def clear_search_filters(self) -> None:
        """Clear active search filters through the shared editor-search helper."""

        _search_controller_for_panel(self).clear_search_filters()

    def _cube_registry_controller(self) -> EditorCubeRegistry:
        """Return the cube registry controller for this panel host."""

        return _cube_registry_for_panel(self)

    def _ordered_buffers(self) -> dict[str, dict]:
        """Return workflow buffers in the current stack order for link refreshes."""

        return _cube_registry_for_panel(self).ordered_buffers()

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Refresh sampler and scheduler link metadata using one shared path."""

        all_buffers = self._ordered_buffers()
        if not all_buffers:
            return
        current_behavior_snapshot = getattr(self, "current_behavior_snapshot", None)
        if not callable(current_behavior_snapshot):
            log_debug(
                _LOGGER,
                "Skipped sampler/scheduler link refresh without snapshot accessor",
            )
            return
        behavior_snapshot = current_behavior_snapshot()
        if behavior_snapshot is None:
            log_debug(
                _LOGGER,
                "Skipped sampler/scheduler link refresh without behavior snapshot",
            )
            return
        link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            stack_order=self._stack_order,
        )
        sanitize_sampler_link_selection(
            all_buffers,
            link_snapshot.sampler_option_map(),
        )
        sanitize_scheduler_link_selection(
            all_buffers,
            link_snapshot.scheduler_option_map(),
        )

    def sanitize_prompt_link_state(self) -> None:
        """Normalize prompt-link groups against the current editor stack order."""

        self._workflow_link_reconciliation_service.sanitize_current_state(
            cube_states=self._cube_states,
            stack_order=self._stack_order,
        )

    def reconcile_prompt_link_state(
        self,
        *,
        previous_cube_states: Mapping[str, object] | None,
        previous_stack_order: list[str] | None,
        cube_states: Mapping[str, object] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Reconcile prompt-link groups across one cube-load or reorder transition."""

        self._workflow_link_reconciliation_service.reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=cube_states,
            current_stack_order=stack_order,
        )

    def apply_manual_node_link_selection(
        self,
        cube_alias: str,
        identity: NodeLinkIdentity,
        from_cube: str | None,
        from_node: str | None,
    ) -> None:
        """Apply one whole-node link combobox selection through the node-link service."""

        if not self._stack_order or not self._cube_states:
            return
        self._workflow_link_reconciliation_service.apply_manual_node_selection(
            cube_states=self._cube_states,
            stack_order=list(self._stack_order),
            cube_alias=cube_alias,
            identity=identity,
            from_cube=from_cube,
            from_node=from_node,
        )

    def _refresh_link_widgets(self) -> None:
        """Refresh node, sampler, and scheduler link widgets in one shared path."""

        update_node_link_widgets = getattr(
            self.meta_registry,
            "update_node_link_widgets",
            None,
        )
        if callable(update_node_link_widgets):
            update_node_link_widgets()
        self.meta_registry.update_sampler_link_widgets()
        self.meta_registry.update_scheduler_link_widgets()

    def refresh_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh link widgets after a cube-scoped workflow change.

        Whole-node selector widths are stack-scoped, so refresh all node-link
        selectors even when only one cube was inserted or rebuilt. Sampler and
        scheduler selectors remain cube-scoped.
        """

        self.meta_registry.update_node_link_widgets()
        self.meta_registry.update_sampler_link_widgets_for_cube(cube_alias)
        self.meta_registry.update_scheduler_link_widgets_for_cube(cube_alias)

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Restore reused prompt-editor widgets from the authoritative workflow buffers."""

        _field_state_controller_for_panel(self).sync_prompt_editor_values_from_buffers()

    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None:
        """Restore prompt-editor widget values for one cube from workflow buffers."""

        _field_state_controller_for_panel(self).sync_prompt_editor_values_for_cube(
            cube_alias
        )

    def _sync_prompt_editor_values_for_widget(self, cube_widget: QWidget) -> None:
        """Restore prompt-editor widget values hosted by one cube widget."""

        _field_state_controller_for_panel(self).sync_prompt_editor_values_for_widget(
            cube_widget
        )

    def reorder_cube_widgets(self):
        """Reattach persistent cube widgets in the active stack order."""

        coordinator = _projection_coordinator_for_panel(self)
        coordinator.reorder_cube_widgets()

    def _get_active_buffer(self):
        """Return the active workflow buffer snapshot used for editor refreshes."""

        try:
            # Assume the last tab/cube buffer is the active one in single-cube mode
            if hasattr(self, "_last_buffer") and self._last_buffer is not None:
                return self._last_buffer
            return {}
        except AttributeError as error:
            log_warning(
                _LOGGER,
                "Failed to read active editor buffer",
                error_type=type(error).__name__,
            )
            return {}

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return this panel's workflow overrides for behavior snapshots."""

        workflow_overrides = None
        try:
            mainwindow = getattr(self, "mainwindow", None)
            session_service = getattr(mainwindow, "workflow_session_service", None)
            workflows = getattr(session_service, "workflows", None)
            workflow = (
                workflows.get(self._workflow_id)
                if isinstance(workflows, MappingABC) and self._workflow_id
                else None
            )
            if workflow is None and hasattr(mainwindow, "get_active_workflow"):
                workflow = mainwindow.get_active_workflow()
            workflow_overrides = getattr(workflow, "global_overrides", None)
        except (AttributeError, RuntimeError, TypeError) as error:
            log_warning(
                _LOGGER,
                "Failed to read workflow overrides for behavior snapshot",
                error_type=type(error).__name__,
            )
            workflow_overrides = None
        return workflow_overrides or {}

    def _build_behavior_snapshot(
        self,
        *,
        search_hidden_keys: set | None = None,
        override_hidden_field_keys: set | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
    ) -> EditorBehaviorSnapshot | None:
        """Resolve and cache the latest node-behavior snapshot for the active panel state."""

        return self._prompt_context_controller.behavior.build(
            search_hidden_keys=search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=node_search_text,
            search_matching_nodes=search_matching_nodes,
        )

    def begin_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Start an explicit behavior snapshot reuse boundary for one refresh flow."""

        self._prompt_context_controller.behavior.begin(reason=reason)

    def end_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Complete the active behavior snapshot reuse boundary when present."""

        self._prompt_context_controller.behavior.end(reason=reason)

    def invalidate_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Drop the active behavior transaction before a state-changing refresh."""

        self._prompt_context_controller.behavior.invalidate(reason=reason)

    def _behavior_snapshot_reuse_key(
        self,
        *,
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set | None,
        override_hidden_field_keys: set | None,
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> tuple[Hashable, ...]:
        """Return the identity key that makes transaction snapshot reuse safe."""

        return self._prompt_context_controller.behavior.reuse_key(
            workflow_overrides=workflow_overrides,
            search_hidden_keys=search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=node_search_text,
            search_matching_nodes=search_matching_nodes,
        )

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest cached behavior snapshot for external toolbar rendering."""

        return self._prompt_context_controller.behavior.current()

    def set_current_behavior_snapshot(
        self,
        snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Publish the latest behavior snapshot through prompt-context ownership."""

        self._prompt_context_controller.behavior.set_current(snapshot)

    def workflow_prompt_context(self) -> WorkflowPromptContext:
        """Return the current workflow context used by prompt-field resolvers."""

        return self._prompt_context_controller.workflow_prompt_context()

    def begin_projection_prompt_context(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> None:
        """Capture immutable prompt-analysis workflow state for one projection."""

        self._prompt_context_controller.begin_projection_prompt_context(
            cube_states=cube_states,
            stack_order=stack_order,
            reason=reason,
        )

    def clear_projection_prompt_context(self, *, reason: str) -> None:
        """Clear projection-scoped prompt state before live editing resumes."""

        self._prompt_context_controller.clear_projection_prompt_context(reason=reason)

    def _build_projection_prompt_context(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> WorkflowPromptContext:
        """Return a workflow prompt context detached from live cube mutation."""

        return self._prompt_context_controller.build_projection_prompt_context(
            cube_states=cube_states,
            stack_order=stack_order,
            reason=reason,
        )

    def _snapshot_prompt_cube_states(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> dict[str, object]:
        """Return cube snapshots whose buffers no longer alias live state."""

        return self._prompt_context_controller.snapshot_prompt_cube_states(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def _snapshot_prompt_workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides detached from live mutation."""

        return self._prompt_context_controller.snapshot_prompt_workflow_overrides()

    def _prompt_workflow_context_for_feature_profiles(self) -> WorkflowPromptContext:
        """Return the active prompt context for feature-profile resolution."""

        return self._prompt_context_controller.prompt_workflow_context_for_feature_profiles()

    def _workflow_prompt_context_key(
        self,
        workflow_overrides: Mapping[str, object],
    ) -> tuple[Hashable, ...]:
        """Return the refresh-scoped identity key for prompt workflow context reuse."""

        return self._prompt_context_controller.workflow_prompt_context_key(
            workflow_overrides
        )

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature:
        """Return the structural signature required by a full editor projection."""

        return _projection_coordinator_for_panel(self).current_projection_signature(
            workflow_id=workflow_id,
            cube_entries=cube_entries,
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def is_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> bool:
        """Return whether this editor surface already renders the signature."""

        return _projection_coordinator_for_panel(self).is_projection_clean(signature)

    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None:
        """Record that the editor surface fully renders the supplied signature."""

        _projection_coordinator_for_panel(self).mark_projection_clean(signature)

    def invalidate_projection(self, *, reason: str) -> None:
        """Mark this editor surface as requiring full projection before reuse."""

        _projection_coordinator_for_panel(self).invalidate_projection(reason=reason)

    def refresh_clean_projection(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Refresh cheap active-state affordances for an already-clean surface."""

        _projection_coordinator_for_panel(self).refresh_clean_projection(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def scheduled_lora_resolver_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
        """Return a narrow resolver callable bound to one prompt field context."""

        return self._prompt_context_controller.scheduled_lora_resolver_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
        )

    def prompt_feature_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile | None:
        """Return the resolved prompt feature profile for one prompt field."""

        return self._prompt_context_controller.prompt_feature_profile_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
            field_style,
        )

    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return prepared prompt feature and syntax profiles for one field."""

        return self._prompt_context_controller.prompt_field_profile_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
            field_style,
        )

    def build_search_corpus_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Build an unfiltered snapshot used as the authoritative search corpus."""

        return _search_controller_for_panel(self).build_search_corpus_snapshot()

    def load_all_cubes(
        self,
        cube_entries,
        cube_states=None,
        stack_order=None,
        projection_signature: EditorSurfaceProjectionSignature | None = None,
        on_complete=None,
    ):
        """Reconcile rendered cube widgets to the latest workflow state."""

        coordinator = _projection_coordinator_for_panel(self)
        self._preset_context_refresh.begin_projection(
            cube_entries=cube_entries,
            cube_states=cube_states,
            stack_order=_projection_stack_order(
                stack_order=stack_order,
                cube_states=cube_states,
            ),
        )

        def projection_completed() -> None:
            """Refresh preset consumers after node projection records model fields."""

            self._preset_context_refresh.refresh(reason="workflow_projection_loaded")
            if on_complete is not None:
                on_complete()

        coordinator.load_all_cubes(
            cube_entries,
            cube_states=cube_states,
            stack_order=stack_order,
            projection_signature=projection_signature,
            on_complete=projection_completed,
        )

    def mark_cube_sections_stale(
        self,
        cube_aliases: Sequence[str],
        *,
        reason: str,
    ) -> bool:
        """Mark rendered cube sections stale before a targeted replacement."""

        return _projection_coordinator_for_panel(self).mark_cube_sections_stale(
            cube_aliases,
            reason=reason,
        )

    def has_pending_visible_projection_commit(self) -> bool:
        """Return whether a background projection is waiting for visible reveal."""

        return bool(
            _projection_coordinator_for_panel(
                self
            ).has_pending_visible_projection_commit()
        )

    def finalize_pending_visible_projection(self) -> bool:
        """Reveal a completed background projection when this panel is active."""

        return bool(
            _projection_coordinator_for_panel(
                self
            ).finalize_pending_visible_projection()
        )

    def is_projection_active(self) -> bool:
        """Return whether this panel still owns full-projection work."""

        return _projection_coordinator_for_panel(self).is_projection_active()

    def insert_cube_section(
        self,
        cube_alias,
        cube_state,
        cube_states=None,
        stack_order=None,
        on_complete=None,
        completion_phase="first_usable",
    ):
        """Insert one newly loaded cube section into the rendered editor surface."""

        coordinator = _projection_coordinator_for_panel(self)
        self._preset_context_refresh.begin_cube_projection(
            cube_alias=cube_alias,
            cube_state=cube_state,
            stack_order=_projection_stack_order(
                stack_order=stack_order,
                cube_states=cube_states,
            ),
        )

        def cube_projection_completed() -> None:
            """Refresh preset consumers after incremental model-field projection."""

            self._preset_context_refresh.refresh(reason="cube_section_inserted")
            if on_complete is not None:
                on_complete()

        coordinator.insert_cube(
            cube_alias,
            cube_state,
            cube_states=cube_states,
            stack_order=stack_order,
            on_complete=cube_projection_completed,
            completion_phase=completion_phase,
        )

    def remove_cube(self, route_key: str) -> None:
        """Remove one cube section from the live editor surface immediately."""

        _projection_coordinator_for_panel(self).remove_cube(route_key)
        self._preset_context_refresh.remove_cube(route_key)

    def rename_cube(self, old_key: str, new_key: str):
        """Rename one cube across widget registries and live link controls."""

        _projection_coordinator_for_panel(self).rename_cube(old_key, new_key)
        self._preset_context_refresh.rename_cube(old_key, new_key)

    def refresh_cube_header(self, alias: str) -> None:
        """Refresh one cube title from the current workflow-owned cube state."""

        _cube_registry_for_panel(self).refresh_cube_header(alias)

    def clear_layout(self):
        """Dispose all rendered cube widgets and reset panel tracking maps."""

        _projection_coordinator_for_panel(self).clear_layout()

    def _remove_cube_widget_from_layout(self, widget):
        """
        Removes the given widget from the layout, detaches it safely, and deletes it.
        """
        if widget is None:
            return
        log_debug(
            _LOGGER,
            "Removing cube widget from editor layout",
            widget_type=type(widget).__name__,
        )
        widget.setParent(None)
        widget.deleteLater()
        cleanup_dead_node_link_widgets = getattr(
            self.meta_registry,
            "cleanup_dead_node_link_widgets",
            None,
        )
        if callable(cleanup_dead_node_link_widgets):
            cleanup_dead_node_link_widgets()

    def _build_cube_widget(self, route_key, cube_state):
        """Build one cube widget through projection-owned lifecycle."""

        return _projection_coordinator_for_panel(self).build_cube_widget(
            route_key,
            cube_state,
        )

    def _begin_build_cube_widget(self, route_key, cube_state):
        """Return a projection-owned incremental cube-section build session."""

        return _projection_coordinator_for_panel(self).begin_build_cube_widget(
            route_key,
            cube_state,
        )

    def _prepare_cube_section_widget(self, route_key: str):
        """Build passive cube-section widgets for projection-owned sessions."""

        builder = getattr(self, "_cube_section_builder", None)
        if builder is None:
            builder = cube_section_builder_for_panel(self)
            setattr(self, "_cube_section_builder", builder)
        return builder.build_cube_section(route_key)

    def _begin_projection_busy(self, message: str = "Loading") -> object | None:
        """Begin shell-owned busy presentation for staged editor projection."""

        mainwindow = getattr(self, "mainwindow", None)
        editor_busy = getattr(mainwindow, "editor_busy", None)
        begin_busy = getattr(editor_busy, "begin", None)
        workflow_session_service = getattr(mainwindow, "workflow_session_service", None)
        workflow_id = str(getattr(workflow_session_service, "active_workflow_id", ""))
        if not workflow_id or not callable(begin_busy):
            return None
        return begin_busy(workflow_id, message=message)

    def _end_projection_busy(self, token: object | None) -> None:
        """End shell-owned busy presentation for staged editor projection."""

        if token is None:
            return
        mainwindow = getattr(self, "mainwindow", None)
        editor_busy = getattr(mainwindow, "editor_busy", None)
        end_busy = getattr(editor_busy, "end", None)
        if callable(end_busy):
            end_busy(token)

    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Register the current live wrapper for one cube node card."""

        _cube_registry_for_panel(self).register_card_wrapper(
            cube_alias,
            node_name,
            wrapper,
        )

    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Remove a card wrapper only while it still owns the registry entry."""

        _cube_registry_for_panel(self).remove_card_wrapper_if_current(
            cube_alias,
            node_name,
            wrapper,
        )

    # === Policy reveal menu logic ===
    def _rebuild_all_cube_visibility_menus(self):
        """Delegate reveal-menu rebuilds to the visibility-menu owner."""

        _cube_visibility_menu_controller_for_panel(self).rebuild_all()

    def _on_cube_visibility_menu_triggered(self, action):
        """Delegate reveal-menu action routing to the visibility-menu owner."""

        _cube_visibility_menu_controller_for_panel(self).route_triggered_action(action)

    def _rebuild_cube_visibility_menu(self, alias: str):
        """Delegate one reveal-menu rebuild to the visibility-menu owner."""

        _cube_visibility_menu_controller_for_panel(self).rebuild(alias)

    def _on_cube_visibility_menu_toggled(self, alias: str, action):
        """Delegate reveal-menu toggle persistence to the visibility-menu owner."""

        _cube_visibility_menu_controller_for_panel(self).route_toggled_action(
            alias, action
        )

    def refresh_node_behavior_state(
        self,
        search_hidden_keys: set | None = None,
        override_hidden_field_keys: set | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
        *,
        reason: BehaviorRefreshReason = "full_workflow_projection",
        use_cached_snapshot: bool = False,
    ):
        """Resolve and apply the latest node-behavior snapshot to UI and buffers."""

        if not self._stack_order or not self._cube_states:
            return
        if node_search_text is not None:
            self._current_node_search_text = node_search_text
        if search_hidden_keys is not None:
            self._current_search_hidden_keys = set(search_hidden_keys)
        if search_matching_nodes is not None:
            self._current_search_matching_nodes = set(search_matching_nodes)
        if (
            not use_cached_snapshot
            and reason in _BEHAVIOR_TRANSACTION_INVALIDATING_REASONS
        ):
            EditorPanel.invalidate_behavior_refresh_transaction(self, reason=reason)
        if not use_cached_snapshot and reason in _PROJECTION_INVALIDATING_REASONS:
            EditorPanel.invalidate_projection(self, reason=reason)

        try:
            last_snapshot = _current_behavior_snapshot_for_panel(self)
            if use_cached_snapshot and last_snapshot is not None:
                snapshot = last_snapshot
            else:
                snapshot_kwargs: dict[str, object] = {
                    "search_hidden_keys": search_hidden_keys,
                    "node_search_text": node_search_text,
                }
                if override_hidden_field_keys is not None:
                    snapshot_kwargs["override_hidden_field_keys"] = (
                        override_hidden_field_keys
                    )
                if search_matching_nodes is not None:
                    snapshot_kwargs["search_matching_nodes"] = search_matching_nodes
                snapshot = self._build_behavior_snapshot(**snapshot_kwargs)
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Failed to build editor behavior snapshot",
                reason=reason,
                use_cached_snapshot=use_cached_snapshot,
                search_hidden_keys=repr(search_hidden_keys),
                node_search_text_length=(
                    0 if node_search_text is None else len(node_search_text)
                ),
                search_matching_nodes=repr(search_matching_nodes),
                error_type=type(error).__name__,
            )
            snapshot = None

        applier = behavior_applier_for_panel(self)

        if snapshot is None:
            applier.restore_previous_state()
            return

        applier.apply_snapshot(snapshot)
        self.refresh_prompt_scene_diagnostics()
        log_debug(
            _LOGGER,
            "Refreshed editor behavior state",
            reason=reason,
            use_cached_snapshot=use_cached_snapshot,
            cube_section_count=len(self._stack_order or []),
        )

    def _clear_layout_recursive(self, layout):
        """Delete widgets from one nested layout tree in place."""

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_layout_recursive(item.layout())

    def is_connection(self, val) -> bool:
        """Return whether one raw input payload represents a node connection."""

        if isinstance(val, list) and len(val) == 2:
            return isinstance(val[0], str) and isinstance(val[1], int)
        if isinstance(val, list) and len(val) == 0:
            return True
        return False

    def build_node_card(
        self,
        node_name: str,
        inputs: dict,
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: dict,
        resolved_behavior,
        display_decision=None,
        alias=None,
        parent: QWidget | None = None,
    ) -> QWidget:
        """Build one node card with focused cold-projection timing."""

        if not hasattr(self, "_node_card_builder"):
            self._node_card_builder = NodeCardBuilder(
                panel=self,
                services=self._services,
                model_choice_snapshot_controller=(
                    self.model_choice_snapshot_controller
                ),
                dimension_preset_source=self.dimension_preset_source,
                node_input_preset_source=self.node_input_preset_source,
                prompt_segment_preset_source=self.prompt_segment_preset_source,
                body_contributors=self._node_card_body_contributors,
            )
        card = self._node_card_builder.build_node_card(
            node_name=node_name,
            inputs=inputs,
            node_type=node_type,
            field_specs=field_specs,
            cube_state=cube_state,
            resolved_behavior=resolved_behavior,
            display_decision=display_decision,
            alias=alias,
            parent=parent,
            prompt_field_inputs=build_node_card_prompt_field_inputs(
                self,
                node_name=node_name,
                field_specs=field_specs,
                alias=alias,
            ),
        )
        return card

    def _cube_widget_is_mostly_visible(
        self,
        route_key: str,
        *,
        visibility_threshold: float = 0.65,
    ) -> bool:
        """Return whether the requested cube section is already mostly visible."""

        return _cube_reveal_controller_for_panel(self).geometry.is_mostly_visible(
            route_key,
            visibility_threshold=visibility_threshold,
        )

    def _cube_reveal_anchor_content_y(self, route_key: str) -> int | None:
        """Return the content-space title/header anchor for one cube section."""

        return _cube_reveal_controller_for_panel(self).geometry.anchor_content_y(
            route_key
        )

    def _cube_header_viewport_anchor_y(self) -> int:
        """Return where cube title/header centers should land in the viewport."""

        return _cube_reveal_controller_for_panel(
            self
        ).geometry.header_viewport_anchor_y()

    def _cube_scroll_target_value(self, route_key: str) -> int | None:
        """Return the scroll value that aligns a cube's title/header anchor."""

        return _cube_reveal_controller_for_panel(self).geometry.scroll_target_value(
            route_key
        )

    def _cube_scroll_target_content_y(self, route_key: str) -> int | None:
        """Return the unclamped content-space target for cube header alignment."""

        return _cube_reveal_controller_for_panel(self).geometry.scroll_target_content_y(
            route_key
        )

    def _emit_current_cube_visible(self, route_key: str) -> None:
        """Emit the visible-cube signal when the target signal is available."""

        _cube_reveal_controller_for_panel(self).emit_current_cube_visible(route_key)

    def scroll_to_cube(
        self,
        route_key: str,
        animated: bool = False,
        duration: int | None = None,
        *,
        only_if_needed: bool = False,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Scroll the panel so the requested cube section becomes visible."""

        _cube_reveal_controller_for_panel(self).scroll_to_cube(
            route_key,
            animated=animated,
            duration=duration,
            only_if_needed=only_if_needed,
            on_finished=on_finished,
        )

    def reveal_new_cube(self, route_key: str) -> None:
        """Reveal a newly loaded cube with optional scroll navigation."""

        _cube_reveal_controller_for_panel(self).reveal_new_cube(route_key)

    def reveal_loaded_cube(self, route_key: str) -> None:
        """Navigate to a newly loaded cube after layout metrics settle."""

        _cube_reveal_controller_for_panel(self).reveal_loaded_cube(route_key)

    def reveal_cube_when_layout_ready(self, route_key: str) -> None:
        """Queue a cube reveal until section height and scroll metrics are stable."""

        _cube_reveal_controller_for_panel(self).reveal_cube_when_layout_ready(route_key)

    def _queue_cube_reveal(self, route_key: str, *, force_navigation: bool) -> None:
        """Queue one cube reveal until section height and scroll metrics are stable."""

        _cube_reveal_controller_for_panel(self).queue_cube_reveal(
            route_key,
            force_navigation=force_navigation,
        )

    def _schedule_pending_cube_reveal_metrics_refresh(self) -> None:
        """Request scroll metrics before completing a pending cube reveal."""

        _cube_reveal_controller_for_panel(
            self
        ).schedule_pending_cube_reveal_metrics_refresh()

    def _complete_pending_cube_reveal(self) -> None:
        """Finish a pending cube reveal after layout and metrics have refreshed."""

        _cube_reveal_controller_for_panel(self).complete_pending_cube_reveal()

    def _cube_section_ready_for_reveal(
        self,
        route_key: str,
        *,
        allow_first_valid: bool = False,
    ) -> bool:
        """Return whether one cube section has stable enough geometry to reveal."""

        return _cube_reveal_controller_for_panel(self).cube_section_ready_for_reveal(
            route_key,
            allow_first_valid=allow_first_valid,
        )

    def _cube_reveal_geometry_signature(self, route_key: str) -> tuple[int, ...] | None:
        """Return reveal metrics that must be stable before loaded-cube navigation."""

        return _cube_reveal_controller_for_panel(self).geometry.readiness_signature(
            route_key
        )

    def scroll_to_input_widget(
        self,
        widget: QWidget,
        animated: bool = True,
        duration: int | None = None,
    ):
        """Scroll the panel so one input widget is centered when possible."""

        _cube_reveal_controller_for_panel(self).scroll_to_input_widget(
            widget,
            animated=animated,
            duration=duration,
        )

    def set_stack_order(self, stack_order: list[str]):
        """Update internal cube order used for scroll tracking."""
        _cube_registry_for_panel(self).set_stack_order(stack_order)
        self._preset_context_refresh.update_cube_order(stack_order)
        self._preset_context_refresh.refresh(reason="stack_order_changed")

    def _on_scroll_updated(self, value):
        """Sync the visible cube tab with the current editor scroll position."""

        _cube_reveal_controller_for_panel(self).on_scroll_updated(int(value))

    def update_all_hidden_fields(self, overrides=None, search_hidden_keys=None):
        """Delegate hidden-field recompute to the extracted controller."""

        _field_sync_controller_for_panel(self).update_all_hidden_fields(
            overrides=overrides,
            search_hidden_keys=search_hidden_keys,
        )

    def set_hidden_field_keys(self, hidden_keys: set):
        """Delegate hidden-field visibility application to the extracted controller."""

        _field_sync_controller_for_panel(self).set_hidden_field_keys(set(hidden_keys))

    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Apply one ephemeral field-search match set to the current row visibility."""

        _field_sync_controller_for_panel(self).set_search_field_match_keys(
            match_keys,
            active=active,
        )

    def highlight_inputs_matching(self, text: str) -> None:
        """Highlight prompt-editor matches through the shared editor-search helper."""

        _search_controller_for_panel(self).highlight_inputs_matching(text)

    def apply_search_result(self, result: EditorSearchResult) -> None:
        """Apply one application-owned search result to the live editor panel."""

        _search_controller_for_panel(self).apply_search_result(result)

    def filter_node_cards_by_search(self, search_text: str) -> None:
        """Filter node-card visibility through the shared editor-search helper."""

        _search_controller_for_panel(self).filter_node_cards_by_search(search_text)

    def search_and_select(self, search_text: str, direction: str = "next") -> None:
        """Cycle editor search matches through the shared editor-search helper."""

        _search_controller_for_panel(self).search_and_select(
            search_text,
            direction=direction,
        )

    def focus_current_search_match(self) -> None:
        """Focus the current editor search match through the shared helper."""

        _search_controller_for_panel(self).focus_current_search_match()


__all__ = ["EditorPanel"]
