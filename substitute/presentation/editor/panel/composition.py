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

"""Compose the editor panel's services, mounted widgets, and controllers."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QWidget
from qfluentwidgets import CheckableMenu  # type: ignore[import-untyped]

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    EditorNodeDefinitionHydrationService,
)
from substitute.application.workflows import (
    WorkflowIssueState,
    WorkflowLinkReconciliationService,
)
from substitute.presentation.editor.panel.widgets.masonry_grid_layout import (
    MasonryGridLayout,
)
from substitute.presentation.editor.utils.create_vbox import create_vbox
from substitute.presentation.widgets.menu_buttons import (
    ToggleTransparentDropDownToolButton,
)
import substitute.presentation.widgets.wheel_intent_controller as wheel_intent

from .behavior.behavior_applier import EditorBehaviorState
from .behavior.panel_ports import behavior_applier_for_panel
from .choice_field_surface_reconciler import ChoiceFieldSurfaceReconciler
from .composition_models import EditorPanelCompositionInputs
from .composition_services import compose_panel_services, compose_preset_sources
from .content_gutter_controller import EditorPanelContentGutterController
from .context.active_model_context import PanelActiveModelContextController
from .context.active_model_snapshot import (
    CachedModelCatalogLookup,
    PanelActiveModelSnapshotController,
)
from .cube_registry import EditorCubeRegistry, EditorCubeRegistryHost
from .cube_reveal_controller import (
    EditorPanelCubeRevealController,
    EditorPanelCubeRevealHost,
)
from .cube_visibility_menu_controller import (
    CubeVisibilityMenuController,
    CubeVisibilityMenuHost,
)
from .field_registry import EditorFieldRegistry
from .field_presentation_controller import EditorPanelFieldPresentationController
from .field_state_controller import EditorPanelFieldStateController
from .field_sync_controller import (
    EditorPanelFieldSyncController,
    EditorPanelFieldSyncHost,
)
from .field_value_change_coordinator import (
    DynamicFieldRefreshHost,
    PanelFieldValueChangeCoordinator,
)
from .lora_metadata_refresh_controller import (
    EditorPanelLoraMetadataRefreshController,
    EditorPanelLoraMetadataRefreshHost,
)
from .meta_registry import MetaRegistry
from .model_choice_snapshot_controller import PanelModelChoiceSnapshotController
from .node_card.mode_controller import NodeCardModeController
from .preset_context_refresh import PanelPresetContextRefreshCoordinator
from .presenter import EditorPanelPresenter
from .projection_coordinator import EditorPanelProjectionCoordinator
from .projection_ports import ProjectionCoordinatorPanelPort
from .prompt.context import EditorPanelPromptContextController
from .prompt.scene_diagnostics import EditorPanelPromptSceneDiagnosticsController
from .prompt_field_state_controller import EditorPanelFieldStateHost
from .runtime_issue_presenter import (
    EditorPanelRuntimeIssueHost,
    EditorPanelRuntimeIssuePresenter,
)
from .search_controller import EditorPanelSearchController, EditorPanelSearchHost
from .widgets.cube_section_builder import cube_section_builder_for_panel
from .widgets.scroll_surface import EditorPanelScrollSurface


def compose_editor_panel(panel: Any, inputs: EditorPanelCompositionInputs) -> None:
    """Install the complete editor runtime onto an initialized QWidget host."""

    panel.setMinimumWidth(1)
    panel._workflow_id = inputs.workflow_id
    panel._services = compose_panel_services(inputs)
    panel._node_card_body_contributors = inputs.node_card_body_contributors
    panel._runtime_issue_presenter = EditorPanelRuntimeIssuePresenter(
        cast(EditorPanelRuntimeIssueHost, panel),
        workflow_issue_state=inputs.workflow_issue_state or WorkflowIssueState(),
        error_presenter=inputs.error_presenter,
    )
    panel.model_choice_snapshot_controller = PanelModelChoiceSnapshotController(
        model_catalog_service=inputs.model_catalog_service,
        model_choice_resolver=inputs.model_choice_resolver,
        ultralytics_thumbnail_associations=inputs.ultralytics_thumbnail_associations,
        panel_context_id_provider=lambda: panel._workflow_id,
    )
    panel.active_model_context_controller = PanelActiveModelContextController()
    active_model_snapshots = PanelActiveModelSnapshotController(
        model_context=panel.active_model_context_controller,
        model_catalog_service=cast(
            CachedModelCatalogLookup | None,
            inputs.model_catalog_service,
        ),
        panel_context_id_provider=lambda: panel._workflow_id,
    )
    panel.active_model_snapshot_controller = active_model_snapshots
    panel._node_definition_hydration_service = EditorNodeDefinitionHydrationService(
        inputs.node_definition_gateway
    )
    preset_sources = compose_preset_sources(inputs, active_model_snapshots)
    panel.dimension_preset_source = preset_sources.dimensions
    panel.node_input_preset_source = preset_sources.node_inputs
    panel.prompt_segment_preset_source = preset_sources.prompt_segments
    _initialize_registries(panel, inputs)
    _mount_scroll_surface(panel)
    _initialize_controllers(panel, inputs)


def _initialize_registries(panel: Any, inputs: EditorPanelCompositionInputs) -> None:
    """Install mutable registries and workflow state owned by the panel runtime."""

    panel.node_link_widgets = {}
    panel.node_link_title_surfaces = {}
    panel.sampler_link_widgets = {}
    panel.scheduler_link_widgets = {}
    panel._workflow_link_reconciliation_service = WorkflowLinkReconciliationService(
        prompt_endpoint_provider=inputs.node_behavior_service,
        node_link_endpoint_provider=inputs.node_behavior_service,
    )
    panel.meta_registry = MetaRegistry(panel)
    panel.cube_widgets = {}
    panel.cube_sections = {}
    panel._cube_states = None
    panel._stack_order = None
    panel.card_wrappers = {}
    panel.cube_headers = {}
    panel.cube_positions = {}
    panel.row_widgets = {}
    panel.col_widgets = {}
    panel._field_registry = EditorFieldRegistry()
    panel.input_widgets_by_field_key = panel._field_registry.widget_map
    panel._preset_context_refresh = PanelPresetContextRefreshCoordinator(
        host=panel,
        model_context=panel.active_model_context_controller,
        model_snapshots=panel.active_model_snapshot_controller,
        dimension_presets=panel.dimension_preset_source,
        node_input_presets=panel.node_input_preset_source,
    )


def _mount_scroll_surface(panel: Any) -> None:
    """Mount prompt and cube layouts inside the editor scroll surface."""

    panel.prompt_area = create_vbox(margins=(0, 6, 7, 6), spacing=0)
    panel.flow_layout = MasonryGridLayout()
    panel._layout = create_vbox(spacing=0)
    panel._layout.setContentsMargins(0, 0, 0, 0)
    panel._layout.addLayout(panel.prompt_area)
    panel._layout.addLayout(panel.flow_layout)
    content = QWidget()
    content.setLayout(panel._layout)
    panel._content_gutter_controller = EditorPanelContentGutterController(content)
    content.setMinimumWidth(1)
    content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    panel.scroll = EditorPanelScrollSurface()
    panel.scroll.setWidgetResizable(True)
    panel.scroll.setWidget(content)
    panel.scroll.setObjectName("EditorScroll")
    panel._cube_reveal_controller = EditorPanelCubeRevealController(
        cast(EditorPanelCubeRevealHost, panel)
    )
    panel._cube_visibility_menu_controller = CubeVisibilityMenuController(
        cast(CubeVisibilityMenuHost, panel)
    )
    panel.scroll.metrics_refreshed.connect(panel._complete_pending_cube_reveal)
    panel.scroll.setStyleSheet(
        "QWidget#EditorScroll { background-color: transparent; border: none; }"
    )
    viewport = panel.scroll.viewport()
    viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    viewport.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    viewport.setStyleSheet("background-color: transparent;")
    viewport.installEventFilter(panel)
    outer = create_vbox(parent=panel, spacing=0)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(panel.scroll)
    panel.setLayout(outer)
    panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    panel.setStyleSheet(
        "EditorPanel { background-color: transparent; }"
        "QSpinBox, QDoubleSpinBox { min-width: 48px; max-width: 48px; height: 32px; }"
    )
    content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    content.setStyleSheet("background-color: transparent;")


def _initialize_controllers(panel: Any, inputs: EditorPanelCompositionInputs) -> None:
    """Install feature controllers after their mounted surfaces exist."""

    panel._hidden_field_keys = set()
    panel._behavior_state = EditorBehaviorState()
    panel._last_card_decisions = panel._behavior_state.last_card_decisions
    panel._last_hidden_field_keys = panel._behavior_state.last_hidden_field_keys
    panel._cube_visibility_btns = cast(
        dict[str, ToggleTransparentDropDownToolButton],
        {},
    )
    panel._cube_visibility_menus = cast(dict[str, CheckableMenu], {})
    panel._cube_registry = EditorCubeRegistry(cast(EditorCubeRegistryHost, panel))
    panel._cube_section_builder = cube_section_builder_for_panel(panel)
    panel._field_value_change_coordinator = PanelFieldValueChangeCoordinator(
        host=cast(DynamicFieldRefreshHost, panel),
        preset_context=panel._preset_context_refresh,
    )
    panel._field_state_controller = EditorPanelFieldStateController(
        cast(EditorPanelFieldStateHost, panel),
        field_value_changed=panel._field_value_change_coordinator.field_value_changed,
    )
    panel._choice_field_surface_reconciler = ChoiceFieldSurfaceReconciler(
        host=panel,
        field_registry=panel._field_registry,
        snapshot_controller=panel.model_choice_snapshot_controller,
        thumbnail_repository_available=inputs.thumbnail_asset_repository is not None,
    )
    panel._field_sync_controller = EditorPanelFieldSyncController(
        cast(EditorPanelFieldSyncHost, panel)
    )
    panel.field_presentation = EditorPanelFieldPresentationController(
        panel,
        field_registry=panel._field_registry,
        preset_context_refresh=panel._preset_context_refresh,
    )
    panel._lora_metadata_refresh_controller = EditorPanelLoraMetadataRefreshController(
        cast(EditorPanelLoraMetadataRefreshHost, panel)
    )
    panel._node_card_mode_controller = NodeCardModeController()
    panel._projection_coordinator = EditorPanelProjectionCoordinator(
        cast(ProjectionCoordinatorPanelPort, panel)
    )
    panel._behavior_applier = behavior_applier_for_panel(panel)
    panel._prompt_context_controller = EditorPanelPromptContextController(panel)
    panel._prompt_scene_diagnostics_controller = (
        EditorPanelPromptSceneDiagnosticsController(panel)
    )
    panel._search_controller = EditorPanelSearchController(
        cast(EditorPanelSearchHost, panel)
    )
    panel._presenter = EditorPanelPresenter(panel)
    panel._preset_context_refresh.refresh(reason="panel_initialized")
    panel._wheel_intent_controller = wheel_intent.WheelIntentController(
        panel,
        wheel_adjustment_mode=inputs.wheel_adjustment_mode,
    )
    panel._search_field_match_keys = cast(set[tuple[str, str, str]] | None, None)
    panel._field_search_active = False
    panel._last_behavior_snapshot = cast(EditorBehaviorSnapshot | None, None)


__all__ = ["EditorPanelCompositionInputs", "compose_editor_panel"]
