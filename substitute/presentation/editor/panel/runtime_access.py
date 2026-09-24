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

"""Resolve focused editor-panel owners for production and lightweight hosts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from substitute.application.node_behavior import EditorBehaviorSnapshot

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
from .preset_context_refresh import PanelPresetContextRefreshCoordinator
from .projection_coordinator import EditorPanelProjectionCoordinator
from .projection_ports import ProjectionCoordinatorPanelPort
from .prompt_field_state_controller import EditorPanelFieldStateHost
from .runtime_issue_presenter import (
    EditorPanelRuntimeIssueHost,
    EditorPanelRuntimeIssuePresenter,
)
from .search_controller import EditorPanelSearchController, EditorPanelSearchHost


def cube_registry_for_panel(panel: object) -> EditorCubeRegistry:
    """Return the cube registry for a production panel or lightweight host."""

    registry = getattr(panel, "_cube_registry", None)
    if registry is None:
        registry = EditorCubeRegistry(cast(EditorCubeRegistryHost, panel))
        setattr(panel, "_cube_registry", registry)
    return cast(EditorCubeRegistry, registry)


def field_registry_for_panel(panel: object) -> EditorFieldRegistry:
    """Return the authoritative rendered field registry for a panel-like host."""

    registry = getattr(panel, "_field_registry", None)
    if registry is None:
        registry = EditorFieldRegistry()
        legacy_widgets = getattr(panel, "input_widgets_by_field_key", None)
        if isinstance(legacy_widgets, Mapping):
            registry.synchronize_from_widget_map(
                cast(Mapping[tuple[str, str, str], object], legacy_widgets)
            )
        setattr(panel, "_field_registry", registry)
        setattr(panel, "input_widgets_by_field_key", registry.widget_map)
    return cast(EditorFieldRegistry, registry)


def cube_reveal_controller_for_panel(
    panel: object,
) -> EditorPanelCubeRevealController:
    """Return the cube reveal controller for a panel-like host."""

    controller = getattr(panel, "_cube_reveal_controller", None)
    if controller is None:
        controller = EditorPanelCubeRevealController(
            cast(EditorPanelCubeRevealHost, panel)
        )
        setattr(panel, "_cube_reveal_controller", controller)
    return cast(EditorPanelCubeRevealController, controller)


def cube_visibility_menu_controller_for_panel(
    panel: object,
) -> CubeVisibilityMenuController:
    """Return the cube visibility-menu owner for a panel-like host."""

    controller = getattr(panel, "_cube_visibility_menu_controller", None)
    if controller is None:
        controller = CubeVisibilityMenuController(cast(CubeVisibilityMenuHost, panel))
        setattr(panel, "_cube_visibility_menu_controller", controller)
    return cast(CubeVisibilityMenuController, controller)


def search_controller_for_panel(panel: object) -> EditorPanelSearchController:
    """Return the search controller for a panel-like host."""

    controller = getattr(panel, "_search_controller", None)
    if controller is None:
        controller = EditorPanelSearchController(cast(EditorPanelSearchHost, panel))
        setattr(panel, "_search_controller", controller)
    return cast(EditorPanelSearchController, controller)


def field_sync_controller_for_panel(panel: object) -> EditorPanelFieldSyncController:
    """Return the field-sync controller for a panel-like host."""

    controller = getattr(panel, "_field_sync_controller", None)
    if controller is None:
        controller = EditorPanelFieldSyncController(
            cast(EditorPanelFieldSyncHost, panel)
        )
        setattr(panel, "_field_sync_controller", controller)
    return cast(EditorPanelFieldSyncController, controller)


def field_state_controller_for_panel(panel: object) -> EditorPanelFieldStateController:
    """Return the field-state controller for a panel-like host."""

    controller = getattr(panel, "_field_state_controller", None)
    if controller is None:
        field_change_coordinator = field_value_change_coordinator_for_panel(panel)
        controller = EditorPanelFieldStateController(
            cast(EditorPanelFieldStateHost, panel),
            field_value_changed=(
                field_change_coordinator.field_value_changed
                if field_change_coordinator is not None
                else None
            ),
        )
        setattr(panel, "_field_state_controller", controller)
    return cast(EditorPanelFieldStateController, controller)


def field_value_change_coordinator_for_panel(
    panel: object,
) -> PanelFieldValueChangeCoordinator | None:
    """Return the value-change coordinator when preset context is available."""

    coordinator = getattr(panel, "_field_value_change_coordinator", None)
    if coordinator is None:
        preset_context = getattr(panel, "_preset_context_refresh", None)
        if preset_context is None:
            return None
        coordinator = PanelFieldValueChangeCoordinator(
            host=cast(DynamicFieldRefreshHost, panel),
            preset_context=cast(PanelPresetContextRefreshCoordinator, preset_context),
        )
        setattr(panel, "_field_value_change_coordinator", coordinator)
    return cast(PanelFieldValueChangeCoordinator, coordinator)


def projection_stack_order(
    *,
    stack_order: Sequence[str] | None,
    cube_states: Mapping[str, object] | None,
) -> Sequence[str] | None:
    """Return the stack order available at a projection boundary."""

    if stack_order is not None:
        return stack_order
    if cube_states is not None:
        return tuple(cube_states)
    return None


def lora_metadata_refresh_controller_for_panel(
    panel: object,
) -> EditorPanelLoraMetadataRefreshController:
    """Return the LoRA metadata refresh controller for a panel-like host."""

    controller = getattr(panel, "_lora_metadata_refresh_controller", None)
    if controller is None:
        controller = EditorPanelLoraMetadataRefreshController(
            cast(EditorPanelLoraMetadataRefreshHost, panel)
        )
        setattr(panel, "_lora_metadata_refresh_controller", controller)
    return cast(EditorPanelLoraMetadataRefreshController, controller)


def runtime_issue_presenter_for_panel(
    panel: object,
) -> EditorPanelRuntimeIssuePresenter:
    """Return the runtime issue presenter for a panel-like host."""

    presenter = getattr(panel, "_runtime_issue_presenter", None)
    if presenter is None:
        presenter = EditorPanelRuntimeIssuePresenter(
            cast(EditorPanelRuntimeIssueHost, panel)
        )
        setattr(panel, "_runtime_issue_presenter", presenter)
    return cast(EditorPanelRuntimeIssuePresenter, presenter)


def projection_coordinator_for_panel(
    panel: object,
) -> EditorPanelProjectionCoordinator:
    """Return the projection coordinator for a panel-like host."""

    coordinator = getattr(panel, "_projection_coordinator", None)
    if coordinator is None:
        coordinator = EditorPanelProjectionCoordinator(
            cast(ProjectionCoordinatorPanelPort, panel)
        )
        setattr(panel, "_projection_coordinator", coordinator)
    return cast(EditorPanelProjectionCoordinator, coordinator)


def current_behavior_snapshot_for_panel(
    panel: object,
) -> EditorBehaviorSnapshot | None:
    """Return the latest behavior snapshot from a panel or lightweight host."""

    current_behavior_snapshot = getattr(panel, "current_behavior_snapshot", None)
    if callable(current_behavior_snapshot):
        return cast(EditorBehaviorSnapshot | None, current_behavior_snapshot())
    return cast(
        EditorBehaviorSnapshot | None,
        getattr(panel, "_last_behavior_snapshot", None),
    )


__all__ = [
    "cube_registry_for_panel",
    "cube_reveal_controller_for_panel",
    "cube_visibility_menu_controller_for_panel",
    "current_behavior_snapshot_for_panel",
    "field_registry_for_panel",
    "field_state_controller_for_panel",
    "field_sync_controller_for_panel",
    "field_value_change_coordinator_for_panel",
    "lora_metadata_refresh_controller_for_panel",
    "projection_coordinator_for_panel",
    "projection_stack_order",
    "runtime_issue_presenter_for_panel",
    "search_controller_for_panel",
]
