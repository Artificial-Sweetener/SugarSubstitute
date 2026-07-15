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

"""Materialize parsed Sugar workflow snapshots into workflow tab UI state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.domain.generation.seed_control import SeedControlState
from substitute.presentation.shell.cube_loader import (
    CubeLoadPresentationIntent,
    CubeLoadUiCallbacks,
    load_cube_async,
)
from substitute.presentation.shell.editor_busy_coordinator import (
    EditorBusyControllerProtocol,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.shell.workflow_snapshot_materialization")


class WorkflowTabItemProtocol(Protocol):
    """Describe workflow-tab item label behavior for snapshot materialization."""

    def setText(self, text: str) -> None:
        """Update the tab label."""


class WorkflowTabBarProtocol(Protocol):
    """Describe workflow-tab lookup behavior for snapshot materialization."""

    itemMap: Mapping[str, WorkflowTabItemProtocol]


class WorkflowSessionServiceProtocol(Protocol):
    """Describe workflow-session state required by snapshot materialization."""

    workflows: dict[str, "WorkflowStateProtocol"]
    active_workflow_id: str


class WorkflowStateProtocol(Protocol):
    """Describe workflow state data mutated by snapshot materialization."""

    global_overrides: dict[str, object]
    global_override_selections: dict[str, bool]
    override_control_states: dict[str, SeedControlState]
    cubes: dict[str, object]


class CubeStackProtocol(Protocol):
    """Describe cube-stack operations used by snapshot materialization."""

    items: list[object]

    def count(self) -> int:
        """Return number of cube tabs."""

    def clear(self) -> None:
        """Remove all cube tabs."""

    def insertTab(self, index: int, **kwargs: object) -> object:
        """Insert a cube tab and return the created tab item."""

    def setCurrentIndex(self, index: int) -> None:
        """Select the current cube tab."""


class EditorPanelProtocol(Protocol):
    """Describe editor-panel behavior used during snapshot materialization."""

    def clear_layout(self) -> None:
        """Remove rendered cube widgets."""


class OverrideManagerProtocol(Protocol):
    """Describe override-manager behavior used during snapshot materialization."""

    def apply_global_overrides(self) -> None:
        """Apply global overrides into workflow and UI state."""


class IconTokenProtocol(Protocol):
    """Describe icon token behavior used for placeholder cube tabs."""

    def icon(self) -> object:
        """Return concrete icon payload."""


class CubeIconProviderProtocol(Protocol):
    """Describe the icon subset used for placeholder cube tabs."""

    CLOSE: IconTokenProtocol


class CubeLoaderProtocol(Protocol):
    """Describe async cube-loader entrypoint used by snapshot materialization."""

    def __call__(
        self,
        callbacks: CubeLoadUiCallbacks,
        *,
        cube_id: str,
        alias_name: str,
        placeholder_index: int,
        buffer_patch: dict[str, object] | None = None,
        reveal_after_load: bool = True,
        presentation_intent: CubeLoadPresentationIntent | None = None,
        on_load_finished: Callable[[str | None], None] | None = None,
    ) -> None:
        """Queue one cube for async load."""


class SnapshotMaterializationView(Protocol):
    """Describe the shell surface consumed by snapshot materialization."""

    workflow_tabbar: WorkflowTabBarProtocol
    workflow_session_service: WorkflowSessionServiceProtocol
    cube_stacks: dict[str, CubeStackProtocol]
    editor_panels: dict[str, EditorPanelProtocol]
    active_override_manager: OverrideManagerProtocol | None
    editor_busy: EditorBusyControllerProtocol
    _pending_cubes: dict[str, int]


class WorkflowSnapshotMaterializer:
    """Own parsed Sugar snapshot projection into one workflow tab."""

    def __init__(
        self,
        view: SnapshotMaterializationView,
        *,
        build_cube_load_ui_callbacks: Callable[..., CubeLoadUiCallbacks],
    ) -> None:
        """Store shell view and cube-loader callback factory."""

        self._view = view
        self._build_cube_load_ui_callbacks = build_cube_load_ui_callbacks

    def materialize(
        self,
        *,
        workflow_id: str,
        workflow_name: str,
        loaded_buffers: Mapping[str, dict[str, object]],
        global_overrides: dict[str, object],
        projects_dir: Path,
        global_override_selections: dict[str, bool] | None = None,
        field_control_states_by_alias: Mapping[
            str,
            Mapping[str, Mapping[str, SeedControlState]],
        ]
        | None = None,
        override_control_states: Mapping[str, SeedControlState] | None = None,
        icon_provider: CubeIconProviderProtocol = FIF,
        cube_loader: CubeLoaderProtocol = load_cube_async,
    ) -> None:
        """Load parsed buffers into an existing active workflow tab."""

        view = self._view
        log_debug(
            _LOGGER,
            "Workflow snapshot materialization started",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            projects_dir=projects_dir,
            alias_count=len(loaded_buffers),
            aliases=list(loaded_buffers.keys()),
            cube_ids=[
                str(buffer.get("cube_id", "")) for buffer in loaded_buffers.values()
            ],
            global_override_count=len(global_overrides),
            global_override_selection_count=len(global_override_selections or {}),
        )
        target_workflow = view.workflow_session_service.workflows[workflow_id]
        target_cube_stack = view.cube_stacks[workflow_id]
        target_editor_panel = view.editor_panels[workflow_id]

        target_workflow.global_overrides = global_overrides
        target_workflow.global_override_selections = dict(
            global_override_selections or {}
        )
        target_workflow.override_control_states = dict(override_control_states or {})
        if view.active_override_manager is not None:
            log_debug(
                _LOGGER,
                "Workflow snapshot applying global overrides",
                workflow_id=workflow_id,
                global_override_count=len(global_overrides),
            )
            view.active_override_manager.apply_global_overrides()

        tab_item = view.workflow_tabbar.itemMap.get(workflow_id)
        if tab_item is not None and workflow_name:
            tab_item.setText(workflow_name)
        log_debug(
            _LOGGER,
            "Workflow snapshot cleared current workflow surfaces",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            had_tab_item=tab_item is not None,
            cube_stack_count_before_clear=target_cube_stack.count(),
        )

        target_cube_stack.clear()
        target_editor_panel.clear_layout()

        loaded_buffer_items = list(loaded_buffers.items())
        if not loaded_buffer_items:
            log_debug(
                _LOGGER,
                "Workflow snapshot materialization ended with no buffers",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
            )
            return

        is_batch_load = len(loaded_buffer_items) > 1
        remaining_loads = len(loaded_buffer_items)
        completed_aliases: list[str] = []
        cube_load_callbacks = self._build_cube_load_ui_callbacks(
            projects_dir=projects_dir
        )
        recipe_load_intent = CubeLoadPresentationIntent(
            select_after_load=False,
            scroll_after_load=False,
        )
        busy_token = view.editor_busy.begin(workflow_id, message="Loading")
        busy_finished = False

        def finish_busy_state() -> None:
            """Clear recipe-load busy state at most once."""

            nonlocal busy_finished
            if busy_finished:
                return
            busy_finished = True
            log_debug(
                _LOGGER,
                "Workflow snapshot ending editor busy state",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
            )
            view.editor_busy.end(busy_token)

        def apply_field_control_states(
            source_alias: str,
            resolved_alias: str | None,
        ) -> None:
            """Apply parsed seed control states to a loaded cube instance."""

            if resolved_alias is None or field_control_states_by_alias is None:
                return
            cube_state = target_workflow.cubes.get(resolved_alias)
            if cube_state is None:
                return
            states = field_control_states_by_alias.get(source_alias)
            if states is None:
                return
            setattr(
                cube_state,
                "field_control_states",
                {
                    str(node): dict(field_states)
                    for node, field_states in states.items()
                },
            )

        def finish_batch_cube_load(
            source_alias: str,
            resolved_alias: str | None,
        ) -> None:
            """Activate one deterministic cube after a recipe-load batch finishes."""

            nonlocal remaining_loads
            apply_field_control_states(source_alias, resolved_alias)
            log_debug(
                _LOGGER,
                "Workflow snapshot cube load callback received",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                resolved_alias=resolved_alias,
                remaining_loads_before=remaining_loads,
            )
            if resolved_alias is not None:
                completed_aliases.append(resolved_alias)
            remaining_loads -= 1
            if remaining_loads > 0:
                return
            finish_busy_state()
            if not completed_aliases:
                return
            activate_loaded_cube = getattr(
                cube_load_callbacks,
                "activate_loaded_cube",
                None,
            )
            if callable(activate_loaded_cube):
                log_debug(
                    _LOGGER,
                    "Workflow snapshot activating final loaded cube",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    completed_aliases=completed_aliases,
                    activated_alias=completed_aliases[-1],
                )
                activate_loaded_cube(workflow_id, completed_aliases[-1])

        def finish_single_cube_load(
            source_alias: str,
            resolved_alias: str | None,
        ) -> None:
            """Apply parsed cube control state and clear busy state."""

            apply_field_control_states(source_alias, resolved_alias)
            finish_busy_state()

        def batch_load_finished_callback(
            source_alias: str,
        ) -> Callable[[str | None], None]:
            """Return a typed callback for one batch cube load."""

            def on_load_finished(resolved_alias: str | None) -> None:
                finish_batch_cube_load(source_alias, resolved_alias)

            return on_load_finished

        def single_load_finished_callback(
            source_alias: str,
        ) -> Callable[[str | None], None]:
            """Return a typed callback for one single cube load."""

            def on_load_finished(resolved_alias: str | None) -> None:
                finish_single_cube_load(source_alias, resolved_alias)

            return on_load_finished

        queued_all_loads = False
        try:
            for alias, buffer_data in loaded_buffer_items:
                log_debug(
                    _LOGGER,
                    "Workflow snapshot queueing cube load",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    alias=alias,
                    cube_id=buffer_data.get("cube_id", ""),
                    is_batch_load=is_batch_load,
                    stack_count_before_insert=target_cube_stack.count(),
                )
                placeholder_item = target_cube_stack.insertTab(
                    target_cube_stack.count(),
                    routeKey=f"loading:{alias}",
                    text="Loading...",
                    icon=icon_provider.CLOSE.icon(),
                )
                placeholder_index = target_cube_stack.items.index(placeholder_item)
                target_cube_stack.setCurrentIndex(placeholder_index)
                view._pending_cubes[alias] = placeholder_index
                log_debug(
                    _LOGGER,
                    "Workflow snapshot inserted cube placeholder",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    alias=alias,
                    cube_id=buffer_data.get("cube_id", ""),
                    placeholder_index=placeholder_index,
                    pending_cubes=dict(view._pending_cubes),
                )
                if is_batch_load:
                    cube_loader(
                        cube_load_callbacks,
                        cube_id=str(buffer_data["cube_id"]),
                        alias_name=alias,
                        placeholder_index=placeholder_index,
                        buffer_patch=buffer_data,
                        reveal_after_load=False,
                        presentation_intent=recipe_load_intent,
                        on_load_finished=batch_load_finished_callback(alias),
                    )
                else:
                    cube_loader(
                        cube_load_callbacks,
                        cube_id=str(buffer_data["cube_id"]),
                        alias_name=alias,
                        placeholder_index=placeholder_index,
                        buffer_patch=buffer_data,
                        reveal_after_load=False,
                        presentation_intent=recipe_load_intent,
                        on_load_finished=single_load_finished_callback(alias),
                    )
            queued_all_loads = True
            log_debug(
                _LOGGER,
                "Workflow snapshot queued all cube loads",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                queued_count=len(loaded_buffer_items),
                pending_cubes=dict(view._pending_cubes),
            )
        finally:
            if not queued_all_loads:
                log_debug(
                    _LOGGER,
                    "Workflow snapshot queueing aborted before all cube loads",
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    pending_cubes=dict(view._pending_cubes),
                )
                finish_busy_state()


__all__ = [
    "SnapshotMaterializationView",
    "WorkflowSnapshotMaterializer",
]
