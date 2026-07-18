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
from typing import Mapping, cast

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    Qt,
    Signal,
)
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QSizePolicy, QWidget
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (
    CheckableMenu,
)
from shiboken6 import isValid as _qt_is_valid

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    EditorNodeDefinitionHydrationService,
    FieldPresentation,
    LiveNodeDefinitionError,
    NodeBehaviorService,
    ResolvedFieldSpec,
    required_node_definition_classes_for_editor_projection,
)
from substitute.application.editor_search import EditorSearchResult
from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.workflows import (
    CubeRuntimeIssue,
    CubeRuntimeIssueSource,
    NodeLinkIdentity,
    WorkflowLinkReconciliationService,
    WorkflowIssueState,
)
from substitute.application.ports import (
    NodeDefinitionGateway,
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import PromptLoraCatalogLookup
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptWheelAdjustmentMode,
    PromptFeatureProfileService,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptSpellcheckService,
    ScheduledLoraProvider,
    WorkflowSceneAnalysis,
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
from substitute.application.overrides import SamplerSchedulerLinkStateService
from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    EDITOR_SECTION_GAP,
    MasonryGridLayout,
)
from substitute.presentation.editor.panel.widgets.fields.load_mask import MaskPicker
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.utils.create_vbox import create_vbox
from substitute.presentation.editor.panel.context.active_model_context import (
    PanelActiveModelContextController,
)
import substitute.presentation.widgets.wheel_intent_controller as wheel_intent
from substitute.presentation.widgets.menu_buttons import (
    ToggleTransparentDropDownToolButton,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)
from .cube_reveal_controller import (
    EditorPanelCubeRevealController,
    EditorPanelCubeRevealHost,
)
from .content_gutter_controller import EditorPanelContentGutterController
from .cube_registry import EditorCubeRegistry, EditorCubeRegistryHost
from .field_sync_controller import (
    EditorPanelFieldSyncController,
    EditorPanelFieldSyncHost,
)
from .field_state_controller import (
    EditorPanelFieldStateController,
    EditorPanelFieldStateHost,
)
from .field_registry import EditorFieldRegistry
from .context.active_model_snapshot import (
    CachedModelCatalogLookup,
    PanelActiveModelSnapshotController,
)
from .lora_metadata_refresh_controller import (
    EditorPanelLoraMetadataRefreshController,
    EditorPanelLoraMetadataRefreshHost,
)
from .model_choice_snapshot_controller import PanelModelChoiceSnapshotController
from .model_field_surface_reconciler import (
    ModelFieldSurfaceReconciler,
    ModelFieldSurfaceReconciliationResult,
)
from .preset_context_refresh import PanelPresetContextRefreshCoordinator
from .presenter import EditorPanelPresenter
from .prompt_context_controller import (
    EditorPanelPromptContextController,
    EditorPanelPromptContextHost,
)
from .prompt_profile_policy import PanelPromptFieldProfileDecision
from .prompt_scene_diagnostics_controller import (
    EditorPanelPromptSceneDiagnosticsController,
    EditorPanelPromptSceneDiagnosticsHost,
)
from .runtime_issue_presenter import (
    EditorPanelRuntimeIssueHost,
    EditorPanelRuntimeIssuePresenter,
)
from .search_controller import EditorPanelSearchController, EditorPanelSearchHost
from .service_bundle import (
    EditorPanelExecutionFactories,
    EditorPanelModelServiceBundle,
    EditorPanelPresetServiceBundle,
    EditorPanelPromptServiceBundle,
    EditorPanelServiceBundle,
)
from .behavior.behavior_applier import EditorBehaviorState
from .behavior.panel_ports import behavior_applier_for_panel
from .projection_coordinator import EditorPanelProjectionCoordinator
from .projection_ports import EditorRefreshPanelProtocol
from .projection_preparation import BehaviorRefreshReason
from .projection_session import EditorSurfaceProjectionSignature
from .widgets.scroll_surface import EditorPanelScrollSurface
from .factories.meta_factories import (
    sanitize_sampler_link_selection,
    sanitize_scheduler_link_selection,
)
from .menus.dimension_preset_menu_source import EditorDimensionPresetMenuSource
from .menus.node_input_preset_menu_source import EditorNodeInputPresetMenuSource
from .meta_registry import MetaRegistry
from .node_card.mode_controller import NodeCardModeController
from ..prompt_editor.features.prompt_segment_preset_source import (
    EditorPromptSegmentPresetMenuSource,
)
from .node_card_builder import NodeCardBuilder, NodeCardPromptFieldInputs
from .widgets.cube_section import CubeSectionBuilder

_LOGGER = get_logger("presentation.editor.panel.view")


def isValid(obj: object) -> bool:  # noqa: N802
    """Return whether one Qt wrapper is valid for panel test hooks."""

    return bool(_qt_is_valid(obj))


def _cube_registry_for_panel(panel: object) -> EditorCubeRegistry:
    """Return a cube registry controller for an editor-panel-like host."""

    registry = getattr(panel, "_cube_registry", None)
    if registry is None:
        registry = EditorCubeRegistry(cast(EditorCubeRegistryHost, panel))
        setattr(panel, "_cube_registry", registry)
    return cast(EditorCubeRegistry, registry)


def _field_registry_for_panel(panel: object) -> EditorFieldRegistry:
    """Return the authoritative rendered field registry for a panel-like host."""

    registry = getattr(panel, "_field_registry", None)
    if registry is None:
        registry = EditorFieldRegistry()
        legacy_widgets = getattr(panel, "input_widgets_by_field_key", None)
        if isinstance(legacy_widgets, MappingABC):
            registry.synchronize_from_widget_map(
                cast(Mapping[tuple[str, str, str], object], legacy_widgets)
            )
        setattr(panel, "_field_registry", registry)
        setattr(panel, "input_widgets_by_field_key", registry.widget_map)
    return cast(EditorFieldRegistry, registry)


def _cube_reveal_controller_for_panel(
    panel: object,
) -> EditorPanelCubeRevealController:
    """Return a cube reveal controller for an editor-panel-like host."""

    controller = getattr(panel, "_cube_reveal_controller", None)
    if controller is None:
        controller = EditorPanelCubeRevealController(
            cast(EditorPanelCubeRevealHost, panel)
        )
        setattr(panel, "_cube_reveal_controller", controller)
    return cast(EditorPanelCubeRevealController, controller)


def _prompt_context_for_panel(panel: object) -> EditorPanelPromptContextController:
    """Return a prompt-context controller for an editor-panel-like host."""

    controller = getattr(panel, "_prompt_context_controller", None)
    if controller is None:
        controller = EditorPanelPromptContextController(
            cast(EditorPanelPromptContextHost, panel)
        )
        setattr(panel, "_prompt_context_controller", controller)
    return cast(EditorPanelPromptContextController, controller)


def _prompt_scene_diagnostics_for_panel(
    panel: object,
) -> EditorPanelPromptSceneDiagnosticsController:
    """Return a scene diagnostics controller for an editor-panel-like host."""

    controller = getattr(panel, "_prompt_scene_diagnostics_controller", None)
    if controller is None:
        controller = EditorPanelPromptSceneDiagnosticsController(
            cast(EditorPanelPromptSceneDiagnosticsHost, panel)
        )
        setattr(panel, "_prompt_scene_diagnostics_controller", controller)
    return cast(EditorPanelPromptSceneDiagnosticsController, controller)


def _search_controller_for_panel(panel: object) -> EditorPanelSearchController:
    """Return a search controller for an editor-panel-like host."""

    controller = getattr(panel, "_search_controller", None)
    if controller is None:
        controller = EditorPanelSearchController(cast(EditorPanelSearchHost, panel))
        setattr(panel, "_search_controller", controller)
    return cast(EditorPanelSearchController, controller)


def _field_sync_controller_for_panel(panel: object) -> EditorPanelFieldSyncController:
    """Return a field-sync controller for an editor-panel-like host."""

    controller = getattr(panel, "_field_sync_controller", None)
    if controller is None:
        controller = EditorPanelFieldSyncController(
            cast(EditorPanelFieldSyncHost, panel)
        )
        setattr(panel, "_field_sync_controller", controller)
    return cast(EditorPanelFieldSyncController, controller)


def _field_state_controller_for_panel(panel: object) -> EditorPanelFieldStateController:
    """Return a field-state controller for an editor-panel-like host."""

    controller = getattr(panel, "_field_state_controller", None)
    if controller is None:
        controller = EditorPanelFieldStateController(
            cast(EditorPanelFieldStateHost, panel),
            field_value_changed=lambda binding, value: cast(
                PanelPresetContextRefreshCoordinator,
                getattr(panel, "_preset_context_refresh"),
            ).update_field_value(
                cube_alias=getattr(binding, "cube_alias", None),
                node_name=getattr(binding, "node_name", None),
                node_type=getattr(binding, "node_type", None),
                field_key=binding.field_key,
                value=value,
            ),
        )
        setattr(panel, "_field_state_controller", controller)
    return cast(EditorPanelFieldStateController, controller)


def _projection_stack_order(
    *,
    stack_order: Sequence[str] | None,
    cube_states: MappingABC[str, object] | None,
) -> Sequence[str] | None:
    """Return the stack order available at a projection boundary."""

    if stack_order is not None:
        return stack_order
    if cube_states is not None:
        return tuple(cube_states)
    return None


def _lora_metadata_refresh_controller_for_panel(
    panel: object,
) -> EditorPanelLoraMetadataRefreshController:
    """Return a LoRA metadata refresh controller for a panel-like host."""

    controller = getattr(panel, "_lora_metadata_refresh_controller", None)
    if controller is None:
        controller = EditorPanelLoraMetadataRefreshController(
            cast(EditorPanelLoraMetadataRefreshHost, panel)
        )
        setattr(panel, "_lora_metadata_refresh_controller", controller)
    return cast(EditorPanelLoraMetadataRefreshController, controller)


def _runtime_issue_presenter_for_panel(
    panel: object,
) -> EditorPanelRuntimeIssuePresenter:
    """Return a runtime issue presenter for an editor-panel-like host."""

    presenter = getattr(panel, "_runtime_issue_presenter", None)
    if presenter is None:
        presenter = EditorPanelRuntimeIssuePresenter(
            cast(EditorPanelRuntimeIssueHost, panel)
        )
        setattr(panel, "_runtime_issue_presenter", presenter)
    return cast(EditorPanelRuntimeIssuePresenter, presenter)


def _projection_coordinator_for_panel(
    panel: object,
) -> EditorPanelProjectionCoordinator:
    """Return a projection coordinator for an editor-panel-like host."""

    coordinator = getattr(panel, "_projection_coordinator", None)
    if coordinator is None:
        coordinator = EditorPanelProjectionCoordinator(
            cast(EditorRefreshPanelProtocol, panel)
        )
        setattr(panel, "_projection_coordinator", coordinator)
    return cast(EditorPanelProjectionCoordinator, coordinator)


def _current_behavior_snapshot_for_panel(
    panel: object,
) -> EditorBehaviorSnapshot | None:
    """Return the latest behavior snapshot from a panel or test double."""

    current_behavior_snapshot = getattr(panel, "current_behavior_snapshot", None)
    if callable(current_behavior_snapshot):
        snapshot = current_behavior_snapshot()
        return cast(EditorBehaviorSnapshot | None, snapshot)
    return cast(
        EditorBehaviorSnapshot | None,
        getattr(panel, "_last_behavior_snapshot", None),
    )


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


def _refresh_prompt_scene_diagnostics_if_available(panel: object) -> None:
    """Refresh scene diagnostics when the panel double exposes the full API."""

    refresh = getattr(panel, "refresh_prompt_scene_diagnostics", None)
    if callable(refresh):
        refresh()


class EditorPanel(QWidget):
    """Render one workflow editor surface and coordinate cube-section refreshes."""

    CUBE_SPACING = EDITOR_SECTION_GAP
    currentCubeVisibleChanged = Signal(str)
    inputImageChanged = Signal(str, str, str)
    inputImageClicked = Signal(str, str, str)
    inputMaskChanged = Signal(str, str, str)
    inputMaskClicked = Signal(str, str, str)
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
        """Finds and refreshes a specific MaskPicker's preview."""
        # Find all MaskPicker widgets that are children of this panel
        inspected_metadata: list[object] = []
        for picker in self.findChildren(MaskPicker):
            meta = picker.property("input_metadata")
            inspected_metadata.append(meta)
            if (
                isinstance(meta, dict)
                and meta.get("cube_alias") == cube_alias
                and meta.get("node_name") == node_name
            ):
                refresh_mask_path = getattr(picker, "refresh_mask_path", None)
                if callable(refresh_mask_path):
                    refresh_mask_path(new_path)
                else:
                    picker.set_mask_path(new_path)
                log_debug(
                    _LOGGER,
                    "Refreshed mask picker thumbnail",
                    cube_alias=cube_alias,
                    node_name=node_name,
                    replacement_path_present=bool(new_path),
                    refresh_method=(
                        "refresh_mask_path"
                        if callable(refresh_mask_path)
                        else "set_mask_path"
                    ),
                )
                return
        log_warning(
            _LOGGER,
            "Failed to refresh mask picker because no matching picker was found",
            cube_alias=cube_alias,
            node_name=node_name,
            replacement_path_present=bool(new_path),
            inspected_count=len(inspected_metadata),
        )

    def refresh_model_metadata(self) -> None:
        """Refresh every model picker widget from current metadata."""

        for entry in _field_registry_for_panel(self).entries():
            if isinstance(entry.widget, ModelPickerField):
                entry.widget.refresh_metadata()
        self._preset_context_refresh.refresh(reason="model_metadata_refreshed")

    def refresh_model_metadata_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Refresh visible model picker state affected by one metadata event."""

        refreshed_count = 0
        for entry in _field_registry_for_panel(self).entries():
            if isinstance(
                entry.widget, ModelPickerField
            ) and entry.widget.refresh_metadata_for_event(event):
                refreshed_count += 1
        self._preset_context_refresh.refresh(reason="model_metadata_event_refreshed")
        return refreshed_count

    def clear_model_thumbnail_caches_for_event(
        self,
        event: ModelMetadataRefreshEvent,
    ) -> int:
        """Clear affected model picker thumbnail caches after image asset updates."""

        cleared_count = 0
        for entry in _field_registry_for_panel(self).entries():
            if isinstance(
                entry.widget, ModelPickerField
            ) and entry.widget.clear_thumbnail_cache_for_event(event):
                cleared_count += 1
        return cleared_count

    def clear_lora_thumbnail_caches(self) -> int:
        """Clear prompt-editor LoRA thumbnail caches owned by this panel."""

        cleared_count = 0
        for prompt_editor in self.findChildren(PromptEditor):
            prompt_editor.clear_lora_thumbnail_cache()
            cleared_count += 1
        return cleared_count

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

        widget = _field_registry_for_panel(self).widget_map.get(
            (cube_alias, node_name, field_key)
        )
        if widget is None:
            log_info(
                _LOGGER,
                "Model-load progress target widget was not found",
                cube_alias=cube_alias,
                node_name=node_name,
                field_key=field_key,
                percent=percent,
                active=active,
            )
            return
        if not isinstance(widget, ModelPickerField):
            log_info(
                _LOGGER,
                "Model-load progress target widget is not a model picker",
                cube_alias=cube_alias,
                node_name=node_name,
                field_key=field_key,
                widget_type=type(widget).__name__,
                percent=percent,
                active=active,
            )
            return
        log_info(
            _LOGGER,
            "Applied model-load progress to model picker",
            cube_alias=cube_alias,
            node_name=node_name,
            field_key=field_key,
            percent=percent,
            active=active,
        )
        widget.set_model_load_progress(percent=percent, active=active)

    def clear_model_field_load_progress(self) -> None:
        """Clear model-load progress from all tracked model picker fields."""

        seen: set[int] = set()
        for widget in _field_registry_for_panel(self).widget_map.values():
            widget_id = id(widget)
            if widget_id in seen:
                continue
            seen.add(widget_id)
            if isinstance(widget, ModelPickerField):
                widget.set_model_load_progress(percent=None, active=False)

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
        user_preset_service: UserPresetService | None = None,
        error_presenter: ErrorReportPresenterProtocol | None = None,
        workflow_issue_state: WorkflowIssueState | None = None,
        workflow_id: str | None = None,
        editor_panel_execution_factories: EditorPanelExecutionFactories | None = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
    ) -> None:
        """Initialize editor panel with live definitions and node-behavior service."""

        super().__init__()
        self.setMinimumWidth(1)
        self._workflow_id = workflow_id
        prompt_services = EditorPanelPromptServiceBundle(
            autocomplete_gateway=prompt_autocomplete_gateway,
            wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            danbooru_url_import_service=danbooru_url_import_service,
            danbooru_wiki_service=danbooru_wiki_service,
            danbooru_image_preview_service=danbooru_image_preview_service,
            danbooru_recent_posts_service=danbooru_recent_posts_service,
            lora_catalog_service=prompt_lora_catalog_service,
            scheduled_lora_provider=scheduled_lora_provider,
            scheduled_lora_service=(
                prompt_scheduled_lora_service or PromptScheduledLoraService()
            ),
            spellcheck_service=prompt_spellcheck_service,
            feature_profile_service=prompt_feature_profile_service,
            thumbnail_asset_repository=thumbnail_asset_repository,
            model_metadata_action_handler=model_metadata_action_handler,
            prompt_task_executor_factory=(
                editor_panel_execution_factories.prompt_task_executor_factory
                if editor_panel_execution_factories is not None
                else None
            ),
            danbooru_lookup_dispatcher_factory=(
                editor_panel_execution_factories.danbooru_lookup_dispatcher_factory
                if editor_panel_execution_factories is not None
                else None
            ),
            model_picker_thumbnail_preload_route_factory=(
                editor_panel_execution_factories.model_picker_thumbnail_preload_route_factory
                if editor_panel_execution_factories is not None
                else None
            ),
        )
        self._services = EditorPanelServiceBundle(
            node_definition_gateway=node_definition_gateway,
            node_behavior_service=node_behavior_service,
            prompt=prompt_services,
            model=EditorPanelModelServiceBundle(
                catalog_service=model_catalog_service,
                choice_resolver=model_choice_resolver,
                thumbnail_asset_repository=thumbnail_asset_repository,
                model_metadata_action_handler=model_metadata_action_handler,
            ),
            presets=EditorPanelPresetServiceBundle(
                user_preset_service=user_preset_service,
            ),
        )
        self._runtime_issue_presenter = EditorPanelRuntimeIssuePresenter(
            cast(EditorPanelRuntimeIssueHost, self),
            workflow_issue_state=workflow_issue_state or WorkflowIssueState(),
            error_presenter=error_presenter,
        )
        self.model_choice_snapshot_controller = PanelModelChoiceSnapshotController(
            model_catalog_service=model_catalog_service,
            model_choice_resolver=model_choice_resolver,
            panel_context_id_provider=lambda: self._workflow_id,
        )
        self.active_model_context_controller = PanelActiveModelContextController()
        active_model_snapshots = PanelActiveModelSnapshotController(
            model_context=self.active_model_context_controller,
            model_catalog_service=cast(
                CachedModelCatalogLookup | None,
                model_catalog_service,
            ),
            panel_context_id_provider=lambda: self._workflow_id,
        )
        self.active_model_snapshot_controller = active_model_snapshots
        self._node_definition_hydration_service = EditorNodeDefinitionHydrationService(
            node_definition_gateway
        )
        self.dimension_preset_source = (
            EditorDimensionPresetMenuSource(
                user_preset_service=user_preset_service,
                active_model_snapshots=active_model_snapshots,
            )
            if user_preset_service is not None
            else None
        )
        self.node_input_preset_source = (
            EditorNodeInputPresetMenuSource(
                user_preset_service=user_preset_service,
                active_model_snapshots=active_model_snapshots,
            )
            if user_preset_service is not None
            else None
        )
        self.prompt_segment_preset_source = (
            EditorPromptSegmentPresetMenuSource(
                user_preset_service=user_preset_service,
                active_model_snapshots=active_model_snapshots,
            )
            if user_preset_service is not None
            else None
        )

        self.node_link_widgets = {}  # (cube_alias, NodeLinkIdentity): ComboBox
        self.node_link_title_surfaces = {}  # (cube_alias, NodeLinkIdentity): surface
        self.sampler_link_widgets = {}  # (cube_alias, node_name): ComboBox
        self.scheduler_link_widgets = {}  # (cube_alias, node_name): ComboBox
        self._workflow_link_reconciliation_service = WorkflowLinkReconciliationService(
            prompt_endpoint_provider=node_behavior_service,
            node_link_endpoint_provider=node_behavior_service,
        )

        self.meta_registry = MetaRegistry(self)

        self.cube_widgets = {}  # alias -> QWidget section for that cube
        self.cube_sections = {}  # alias -> QWidget section used by scroll/reveal
        self._cube_states = None  # Dict of alias -> CubeState
        self._stack_order = None  # List of aliases in workflow order
        # Map of (alias, node_name) -> card wrapper QWidget for fast visibility toggling
        self.card_wrappers = {}

        self.cube_headers = {}  # routeKey -> QLabel
        self.cube_positions = {}  # routeKey → y()

        # === Input row and column mappings for reliable hide/show logic ===
        self.row_widgets = {}  # field_key -> (divider_widget, row_widget)
        self.col_widgets = {}  # field_key -> (row_container, column_widget)
        self._field_registry = EditorFieldRegistry()
        self.input_widgets_by_field_key: dict[tuple[str, str, str], QWidget] = cast(
            dict[tuple[str, str, str], QWidget],
            self._field_registry.widget_map,
        )
        self._preset_context_refresh = PanelPresetContextRefreshCoordinator(
            host=self,
            model_context=self.active_model_context_controller,
            model_snapshots=self.active_model_snapshot_controller,
            dimension_presets=self.dimension_preset_source,
            node_input_presets=self.node_input_preset_source,
        )

        # === Input/prompt layout structures ===

        # Prompt area: left-aligned with custom padding
        self.prompt_area = create_vbox(margins=(0, 6, 7, 6), spacing=0)

        # Flow layout for node cards (replaces columns)
        self.flow_layout = MasonryGridLayout()

        # === Full content layout (prompt area + flow layout) ===
        self._layout = create_vbox(spacing=0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addLayout(self.prompt_area)
        self._layout.addLayout(self.flow_layout)

        content = QWidget()
        content.setLayout(self._layout)
        self._content_gutter_controller = EditorPanelContentGutterController(content)
        content.setMinimumWidth(1)
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # === Application-owned scroll container for content ===
        self.scroll = EditorPanelScrollSurface()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(content)
        self.scroll.setObjectName("EditorScroll")
        self._cube_reveal_controller = EditorPanelCubeRevealController(
            cast(EditorPanelCubeRevealHost, self)
        )
        self.scroll.metrics_refreshed.connect(self._complete_pending_cube_reveal)
        self.scroll.setStyleSheet(
            """
            QWidget#EditorScroll {
                background-color: transparent;
                border: none;
            }
        """
        )

        # Ensure scroll area viewport is transparent
        viewport = self.scroll.viewport()
        viewport.setAttribute(Qt.WA_TranslucentBackground)
        viewport.setAttribute(Qt.WA_StyledBackground)
        viewport.setStyleSheet("background-color: transparent;")
        viewport.installEventFilter(self)

        # === Outer container layout ===
        outer = create_vbox(parent=self, spacing=0)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)
        self.setLayout(outer)
        # === Background and styling ===
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")
        content.setAttribute(Qt.WA_TranslucentBackground)
        content.setStyleSheet("background-color: transparent;")

        self.setStyleSheet(
            """
            EditorPanel {
                background-color: transparent;
            }

            QSpinBox, QDoubleSpinBox {
                min-width: 48px;
                max-width: 48px;
                height: 32px;
            }
        """
        )

        # === Global hidden fields by key name ===
        self._hidden_field_keys = set()
        self._behavior_state = EditorBehaviorState()
        # Panel-owned mirrors used by current lifecycle controllers.
        self._last_card_decisions = self._behavior_state.last_card_decisions
        self._last_hidden_field_keys = self._behavior_state.last_hidden_field_keys

        # === Per-cube policy reveal UI ===
        self._cube_visibility_btns: dict[str, ToggleTransparentDropDownToolButton] = {}
        self._cube_visibility_menus: dict[str, CheckableMenu] = {}
        self._cube_registry = EditorCubeRegistry(cast(EditorCubeRegistryHost, self))
        self._cube_section_builder = CubeSectionBuilder(self)
        self._field_state_controller = EditorPanelFieldStateController(
            cast(EditorPanelFieldStateHost, self),
            field_value_changed=lambda binding, value: (
                self._preset_context_refresh.update_field_value(
                    cube_alias=getattr(binding, "cube_alias", None),
                    node_name=getattr(binding, "node_name", None),
                    node_type=getattr(binding, "node_type", None),
                    field_key=binding.field_key,
                    value=value,
                )
            ),
        )
        self._model_field_surface_reconciler = ModelFieldSurfaceReconciler(
            host=self,
            field_registry=self._field_registry,
            snapshot_controller=self.model_choice_snapshot_controller,
            thumbnail_repository_available=thumbnail_asset_repository is not None,
        )
        self._field_sync_controller = EditorPanelFieldSyncController(
            cast(EditorPanelFieldSyncHost, self)
        )
        self._lora_metadata_refresh_controller = (
            EditorPanelLoraMetadataRefreshController(
                cast(EditorPanelLoraMetadataRefreshHost, self)
            )
        )
        self._node_card_mode_controller = NodeCardModeController()
        self._projection_coordinator = EditorPanelProjectionCoordinator(self)
        self._behavior_applier = behavior_applier_for_panel(self)
        self._prompt_context_controller = EditorPanelPromptContextController(
            cast(EditorPanelPromptContextHost, self)
        )
        self._prompt_scene_diagnostics_controller = (
            EditorPanelPromptSceneDiagnosticsController(
                cast(EditorPanelPromptSceneDiagnosticsHost, self)
            )
        )
        self._search_controller = EditorPanelSearchController(
            cast(EditorPanelSearchHost, self)
        )
        self._presenter = EditorPanelPresenter(self)
        self._preset_context_refresh.refresh(reason="panel_initialized")
        self._wheel_intent_controller = wheel_intent.WheelIntentController(
            self,
            wheel_adjustment_mode=wheel_adjustment_mode,
        )

        self._search_field_match_keys: set[tuple[str, str, str]] | None = None
        self._field_search_active = False
        self._last_behavior_snapshot: EditorBehaviorSnapshot | None = None

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

        return self._services.prompt.scheduled_lora_service_or_default()

    @property
    def scheduled_lora_provider(self) -> ScheduledLoraProvider | None:
        """Return the optional scheduled-LoRA provider for prompt contexts."""

        return self._services.prompt.scheduled_lora_provider

    @property
    def prompt_spellcheck_service(self) -> PromptSpellcheckService | None:
        """Return the optional prompt spellcheck service for host integrations."""

        return self._services.prompt.spellcheck_service

    @property
    def prompt_feature_profile_service(self) -> PromptFeatureProfileService | None:
        """Return the optional prompt feature-profile service for prompt contexts."""

        return self._services.prompt.feature_profile_service

    def configure_wheel_intent_for_widget(self, widget: QWidget) -> None:
        """Attach shared wheel-intent policy to wheel-capable controls."""

        self._wheel_intent_controller.configure_widget(widget)
        for prompt_editor in self._prompt_wheel_widgets(widget):
            self._configure_prompt_scene_diagnostics(prompt_editor)
            self._configure_prompt_text_search_refresh(prompt_editor)

    def _configure_prompt_scene_diagnostics(
        self,
        prompt_editor: PromptEditor,
    ) -> None:
        """Attach workflow-scene diagnostics refresh to one prompt editor."""

        _prompt_scene_diagnostics_for_panel(self).configure_prompt_scene_diagnostics(
            prompt_editor
        )

    def _schedule_prompt_scene_diagnostics(self) -> None:
        """Defer scene diagnostics until prompt text has reached workflow buffers."""

        _prompt_scene_diagnostics_for_panel(self).schedule_prompt_scene_diagnostics()

    def _refresh_scheduled_prompt_scene_diagnostics(self) -> None:
        """Apply one deferred prompt-scene diagnostics refresh."""

        _prompt_scene_diagnostics_for_panel(
            self
        ).refresh_scheduled_prompt_scene_diagnostics()

    def _configure_prompt_text_search_refresh(
        self,
        prompt_editor: PromptEditor,
    ) -> None:
        """Attach active search recomputation to one prompt editor."""

        _search_controller_for_panel(self).configure_prompt_text_search_refresh(
            prompt_editor
        )

    def _schedule_text_search_refresh(self) -> None:
        """Schedule active text-search ranges to be rebuilt after prompt edits."""

        _search_controller_for_panel(self).schedule_text_search_refresh()

    def _refresh_scheduled_text_search(self) -> None:
        """Recompute active editor text-search highlights from the latest buffers."""

        _search_controller_for_panel(self).refresh_scheduled_text_search()

    def refresh_prompt_scene_diagnostics(self) -> None:
        """Push current workflow scene diagnostics into all live prompt editors."""

        _prompt_scene_diagnostics_for_panel(self).refresh_prompt_scene_diagnostics()

    def _clear_prompt_scene_diagnostics(self) -> None:
        """Clear scene diagnostics from all live prompt editors."""

        _prompt_scene_diagnostics_for_panel(self).clear_prompt_scene_diagnostics()

    def _current_prompt_scene_analysis(self) -> WorkflowSceneAnalysis | None:
        """Return current workflow scene analysis when editor state is ready."""

        return _prompt_scene_diagnostics_for_panel(self).current_prompt_scene_analysis()

    def _handle_prompt_scene_queue_requested(self, scene_key: str) -> None:
        """Forward one prompt scene queue request when the scene is runnable."""

        _prompt_scene_diagnostics_for_panel(self).handle_prompt_scene_queue_requested(
            scene_key
        )

    def _prompt_wheel_widgets(self, widget: QWidget) -> tuple[PromptEditor, ...]:
        """Return prompt editors contained by one field widget."""

        widgets: list[PromptEditor] = []
        if isinstance(widget, PromptEditor):
            widgets.append(widget)
        widgets.extend(widget.findChildren(PromptEditor))
        unique_widgets: list[PromptEditor] = []
        seen_ids: set[int] = set()
        for candidate in widgets:
            candidate_id = id(candidate)
            if candidate_id in seen_ids:
                continue
            seen_ids.add(candidate_id)
            unique_widgets.append(candidate)
        return tuple(unique_widgets)

    def handle_external_wheel(self, event: QWheelEvent) -> None:
        """Apply a wheel event routed from adjacent workspace navigation chrome."""

        self._cancel_active_cube_reveal_scroll()
        viewport = self.scroll.viewport()
        local_position = viewport.mapFromGlobal(event.globalPosition().toPoint())
        if not viewport.rect().contains(local_position):
            local_position = viewport.rect().center()
        global_position = viewport.mapToGlobal(local_position)
        forwarded_event = QWheelEvent(
            QPointF(local_position),
            QPointF(global_position),
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
        )
        QApplication.sendEvent(viewport, forwarded_event)
        if forwarded_event.isAccepted():
            event.accept()
            return
        event.ignore()

    def clear_search_filters(self) -> None:
        """Clear active search filters through the shared editor-search helper."""

        _search_controller_for_panel(self).clear_search_filters()

    def _cube_registry_controller(self) -> EditorCubeRegistry:
        """Return the cube registry controller for this panel host."""

        return _cube_registry_for_panel(self)

    def _ordered_buffers(self) -> dict[str, dict]:
        """Return workflow buffers in the current stack order for link refreshes."""

        return _cube_registry_for_panel(self).ordered_buffers()

    def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
        """Hydrate live node definitions before correctness-sensitive projection."""

        if not self._stack_order or not self._cube_states:
            return
        result = self._node_definition_hydration_service.hydrate_for_projection(
            cube_states=self._cube_states,
            stack_order=self._stack_order,
        )
        log_info(
            _LOGGER,
            "Editor projection node definition hydration completed",
            reason=reason,
            requested_count=len(result.requested) if result is not None else 0,
            unavailable_count=len(result.unavailable) if result is not None else 0,
        )

    def begin_live_node_definition_report_projection(self) -> None:
        """Start a projection-scoped live metadata report dedupe window."""

        _runtime_issue_presenter_for_panel(
            self
        ).begin_live_node_definition_report_projection()

    def register_projection_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        source: CubeRuntimeIssueSource,
    ) -> bool:
        """Register a cube-attributed projection hydration failure."""

        return _runtime_issue_presenter_for_panel(
            self
        ).register_projection_live_node_definition_error(
            error,
            reason=reason,
            source=source,
        )

    def present_recoverable_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show a deduplicated non-fatal live metadata report for a cube issue."""

        _runtime_issue_presenter_for_panel(
            self
        ).present_recoverable_live_node_definition_error(error, reason=reason)

    def _present_live_node_definition_error_once(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show one live metadata report unless the same report was already shown."""

        _runtime_issue_presenter_for_panel(
            self
        ).present_live_node_definition_error_once(error, reason=reason)

    def clear_projection_runtime_issues(self) -> None:
        """Clear projection-owned runtime issues after successful hydration."""

        _runtime_issue_presenter_for_panel(self).clear_projection_runtime_issues()

    def set_cube_runtime_issues(
        self,
        cube_alias: str,
        issues: Sequence[CubeRuntimeIssue],
    ) -> None:
        """Apply runtime issue presentation to one rendered cube section."""

        _runtime_issue_presenter_for_panel(self).set_cube_runtime_issues(
            cube_alias,
            issues,
        )

    def clear_cube_runtime_issues(self, cube_alias: str) -> None:
        """Clear runtime issues for one cube and refresh its rendered section."""

        _runtime_issue_presenter_for_panel(self).clear_cube_runtime_issues(cube_alias)

    def cube_runtime_issues(
        self,
        cube_alias: str,
    ) -> tuple[CubeRuntimeIssue, ...]:
        """Return locally projected runtime issues for one cube."""

        return _runtime_issue_presenter_for_panel(self).cube_runtime_issues(cube_alias)

    def cube_runtime_error_aliases(self) -> tuple[str, ...]:
        """Return aliases with error-severity runtime issues."""

        return _runtime_issue_presenter_for_panel(self).cube_runtime_error_aliases()

    def _sync_cube_runtime_issues_from_state(self) -> None:
        """Refresh local issue projection from workflow-owned issue state."""

        _runtime_issue_presenter_for_panel(self).sync_cube_runtime_issues_from_state()

    def _apply_cube_runtime_issues_to_widget(self, cube_alias: str) -> None:
        """Apply issue wash state to one cube section widget when it exists."""

        _runtime_issue_presenter_for_panel(self).apply_cube_runtime_issues_to_widget(
            cube_alias
        )

    def _apply_cube_runtime_issues_to_stack(
        self,
        cube_alias: str,
        severity: str | None,
    ) -> None:
        """Apply issue severity to the matching cube-stack tab when available."""

        _runtime_issue_presenter_for_panel(self).apply_cube_runtime_issues_to_stack(
            cube_alias,
            severity,
        )

    def _build_error_cube_widget(self, route_key: str, cube_state: object) -> QWidget:
        """Build a cube section that exposes recoverable runtime issues only."""

        return _runtime_issue_presenter_for_panel(self).build_error_cube_widget(
            route_key,
            cube_state,
        )

    def _present_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
    ) -> None:
        """Show the blocking live-metadata report through the injected presenter."""

        _runtime_issue_presenter_for_panel(self).present_live_node_definition_error(
            error,
            reason=reason,
        )

    def refresh_projection_after_node_definition_update(
        self,
        *,
        refreshed_node_classes: Sequence[str],
    ) -> bool:
        """Rebuild rendered widgets when a late node definition affects them."""

        if not self._stack_order or not self._cube_states:
            return False
        normalized_refreshed = {
            node_class.strip()
            for node_class in refreshed_node_classes
            if isinstance(node_class, str) and node_class.strip()
        }
        if not normalized_refreshed:
            return False
        try:
            required_node_classes = set(
                required_node_definition_classes_for_editor_projection(
                    self._ordered_projection_buffers()
                )
            )
            affected_node_classes = tuple(
                sorted(required_node_classes.intersection(normalized_refreshed))
            )
        except (RuntimeError, TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Rebuilding editor projection after node definition refresh detection failed",
                refreshed_node_classes=tuple(sorted(normalized_refreshed)),
                error_type=type(error).__name__,
            )
            affected_node_classes = tuple(sorted(normalized_refreshed))
        if not affected_node_classes:
            log_debug(
                _LOGGER,
                "Skipped editor projection rebuild for unrelated node definition refresh",
                refreshed_node_classes=tuple(sorted(normalized_refreshed)),
            )
            return False

        cube_entries = self._current_cube_entries_for_projection()
        if not cube_entries:
            return False
        affected_cube_aliases = self._cube_aliases_for_node_classes(
            affected_node_classes
        )
        coordinator = _projection_coordinator_for_panel(self)
        mark_stale = getattr(coordinator, "mark_cube_sections_stale", None)
        active_build_affected = False
        if callable(mark_stale):
            active_build_affected = bool(
                mark_stale(
                    affected_cube_aliases,
                    reason="node_definition_changed",
                )
            )
        EditorPanel.invalidate_projection(self, reason="node_definition_changed")
        self.load_all_cubes(
            cube_entries,
            cube_states=self._cube_states,
            stack_order=self._stack_order,
            projection_signature=None,
        )
        log_info(
            _LOGGER,
            "Rebuilt editor projection after node definition refresh",
            affected_node_classes=affected_node_classes,
            affected_cube_aliases=tuple(affected_cube_aliases),
            refreshed_node_classes=tuple(sorted(normalized_refreshed)),
            cube_section_count=len(cube_entries),
            active_build_affected=active_build_affected,
        )
        return True

    def reconcile_model_fields_after_node_definition_update(
        self,
        *,
        refreshed_node_classes: Sequence[str],
    ) -> ModelFieldSurfaceReconciliationResult:
        """Apply refreshed model options to existing controls without projection."""

        result = self._model_field_surface_reconciler.reconcile(refreshed_node_classes)
        if result.reconciled_field_count:
            self._preset_context_refresh.refresh(reason="model_options_changed")
        return result

    def _cube_aliases_for_node_classes(
        self,
        node_classes: Sequence[str],
    ) -> tuple[str, ...]:
        """Return cube aliases whose buffers contain one of the node classes."""

        if not self._cube_states or not self._stack_order:
            return ()
        target_classes = set(node_classes)
        aliases: list[str] = []
        for alias in self._stack_order:
            cube_state = self._cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", None)
            nodes = buffer.get("nodes", {}) if isinstance(buffer, MappingABC) else {}
            if not isinstance(nodes, MappingABC):
                continue
            for node_data in nodes.values():
                if not isinstance(node_data, MappingABC):
                    continue
                if node_data.get("class_type") in target_classes:
                    aliases.append(alias)
                    break
        return tuple(aliases)

    def _ordered_projection_buffers(self) -> dict[str, Mapping[str, object]]:
        """Return active cube buffers in stack order for projection dependency checks."""

        return _cube_registry_for_panel(self).ordered_projection_buffers()

    def _current_cube_entries_for_projection(self) -> list[tuple[str, object]]:
        """Return active cube entries in stack order for projection rebuilds."""

        return _cube_registry_for_panel(self).current_cube_entries_for_projection()

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

        return _prompt_context_for_panel(self).build_behavior_snapshot(
            search_hidden_keys=search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=node_search_text,
            search_matching_nodes=search_matching_nodes,
        )

    def begin_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Start an explicit behavior snapshot reuse boundary for one refresh flow."""

        _prompt_context_for_panel(self).begin_behavior_refresh_transaction(
            reason=reason
        )

    def end_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Complete the active behavior snapshot reuse boundary when present."""

        _prompt_context_for_panel(self).end_behavior_refresh_transaction(reason=reason)

    def invalidate_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Drop the active behavior transaction before a state-changing refresh."""

        _prompt_context_for_panel(self).invalidate_behavior_refresh_transaction(
            reason=reason
        )

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

        return _prompt_context_for_panel(self).behavior_snapshot_reuse_key(
            workflow_overrides=workflow_overrides,
            search_hidden_keys=search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=node_search_text,
            search_matching_nodes=search_matching_nodes,
        )

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest cached behavior snapshot for external toolbar rendering."""

        return _prompt_context_for_panel(self).current_behavior_snapshot()

    def set_current_behavior_snapshot(
        self,
        snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Publish the latest behavior snapshot through prompt-context ownership."""

        _prompt_context_for_panel(self).set_current_behavior_snapshot(snapshot)

    def workflow_prompt_context(self) -> WorkflowPromptContext:
        """Return the current workflow context used by prompt-field resolvers."""

        return _prompt_context_for_panel(self).workflow_prompt_context()

    def begin_projection_prompt_context(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> None:
        """Capture immutable prompt-analysis workflow state for one projection."""

        _prompt_context_for_panel(self).begin_projection_prompt_context(
            cube_states=cube_states,
            stack_order=stack_order,
            reason=reason,
        )

    def clear_projection_prompt_context(self, *, reason: str) -> None:
        """Clear projection-scoped prompt state before live editing resumes."""

        _prompt_context_for_panel(self).clear_projection_prompt_context(reason=reason)

    def _build_projection_prompt_context(
        self,
        *,
        cube_states: MappingABC[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> WorkflowPromptContext:
        """Return a workflow prompt context detached from live cube mutation."""

        return _prompt_context_for_panel(self).build_projection_prompt_context(
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

        return _prompt_context_for_panel(self).snapshot_prompt_cube_states(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def _snapshot_prompt_workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides detached from live mutation."""

        return _prompt_context_for_panel(self).snapshot_prompt_workflow_overrides()

    def _prompt_workflow_context_for_feature_profiles(self) -> WorkflowPromptContext:
        """Return the active prompt context for feature-profile resolution."""

        return _prompt_context_for_panel(
            self
        ).prompt_workflow_context_for_feature_profiles()

    def _workflow_prompt_context_key(
        self,
        workflow_overrides: Mapping[str, object],
    ) -> tuple[Hashable, ...]:
        """Return the refresh-scoped identity key for prompt workflow context reuse."""

        return _prompt_context_for_panel(self).workflow_prompt_context_key(
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

        return _prompt_context_for_panel(self).scheduled_lora_resolver_for_prompt(
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

        return _prompt_context_for_panel(self).prompt_feature_profile_for_prompt(
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

        return _prompt_context_for_panel(self).prompt_field_profile_for_prompt(
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
            builder = CubeSectionBuilder(self)
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
        """Delegate reveal-menu rebuilds to the cube reveal controller."""

        _cube_reveal_controller_for_panel(self).rebuild_all_cube_visibility_menus()

    def _on_cube_visibility_menu_triggered(self, action):
        """Delegate reveal-menu action routing to the cube reveal controller."""

        _cube_reveal_controller_for_panel(self).on_cube_visibility_menu_triggered(
            action
        )

    def _rebuild_cube_visibility_menu(self, alias: str):
        """Delegate one reveal-menu rebuild to the cube reveal controller."""

        _cube_reveal_controller_for_panel(self).rebuild_cube_visibility_menu(alias)

    def _on_cube_visibility_menu_toggled(self, alias: str, action):
        """Delegate reveal-menu toggle persistence to the cube reveal controller."""

        _cube_reveal_controller_for_panel(self).on_cube_visibility_menu_toggled(
            alias,
            action,
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
        _refresh_prompt_scene_diagnostics_if_available(self)
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

    def _node_card_prompt_field_inputs(
        self,
        *,
        node_name: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        alias: str | None,
    ) -> dict[str, NodeCardPromptFieldInputs]:
        """Prepare Phase 13 prompt-context inputs for one node-card build."""

        prompt_inputs: dict[str, NodeCardPromptFieldInputs] = {}
        for field_key, field_spec in field_specs.items():
            field_behavior = field_spec.field_behavior
            if field_behavior.presentation != FieldPresentation.PROMPT_BOX:
                continue
            prompt_inputs[field_key] = NodeCardPromptFieldInputs(
                scheduled_lora_resolver=self.scheduled_lora_resolver_for_prompt(
                    alias,
                    node_name,
                    field_key,
                ),
                prompt_field_profile=self.prompt_field_profile_for_prompt(
                    alias,
                    node_name,
                    field_key,
                    field_behavior.style,
                ),
            )
        return prompt_inputs

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
            prompt_field_inputs=EditorPanel._node_card_prompt_field_inputs(
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

        return _cube_reveal_controller_for_panel(self).cube_widget_is_mostly_visible(
            route_key,
            visibility_threshold=visibility_threshold,
        )

    def _cube_reveal_anchor_content_y(self, route_key: str) -> int | None:
        """Return the content-space title/header anchor for one cube section."""

        return _cube_reveal_controller_for_panel(self).cube_reveal_anchor_content_y(
            route_key
        )

    def _cube_header_viewport_anchor_y(self) -> int:
        """Return where cube title/header centers should land in the viewport."""

        return _cube_reveal_controller_for_panel(self).cube_header_viewport_anchor_y()

    def _cube_scroll_target_value(self, route_key: str) -> int | None:
        """Return the scroll value that aligns a cube's title/header anchor."""

        return _cube_reveal_controller_for_panel(self).cube_scroll_target_value(
            route_key
        )

    def _cube_scroll_target_content_y(self, route_key: str) -> int | None:
        """Return the unclamped content-space target for cube header alignment."""

        return _cube_reveal_controller_for_panel(self).cube_scroll_target_content_y(
            route_key
        )

    def _emit_current_cube_visible(self, route_key: str) -> None:
        """Emit the visible-cube signal when the target signal is available."""

        _cube_reveal_controller_for_panel(self).emit_current_cube_visible(route_key)

    def _animate_scrollbar_value(
        self,
        *,
        scrollbar: object,
        target_value: int,
        animated: bool,
        duration_ms: int,
        animation_attr_name: str,
        suppress_tab_sync: bool,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Move one scrollbar either immediately or through shared Fluent motion."""

        _cube_reveal_controller_for_panel(self)._animate_scrollbar_value(
            scrollbar=scrollbar,
            target_value=target_value,
            animated=animated,
            duration_ms=duration_ms,
            animation_attr_name=animation_attr_name,
            suppress_tab_sync=suppress_tab_sync,
            on_finished=on_finished,
        )

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

        return _cube_reveal_controller_for_panel(self).cube_reveal_geometry_signature(
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
