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

"""Apply live shell layout chrome state for workspace routes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QObject, QTimer

from substitute.presentation.resources.app_icon import AppIcon
from substitute.domain.workspace_snapshot.models import (
    ShellLayoutSnapshot,
    WindowGeometrySnapshot,
)
from substitute.presentation.shell.comfy_runtime_actions import (
    comfy_runtime_actions_for,
)
from substitute.presentation.shell.shell_layout_state import (
    LiveShellLayoutMeasurements,
    build_shell_layout_restore_plan,
    canonical_layout_from_measurements,
)
from substitute.presentation.shell.shell_layout_trace import (
    log_editor_width_trace as emit_editor_width_trace,
    safe_trace_splitter_sizes,
    safe_trace_width,
)
from substitute.presentation.shell.main_window_startup_trace import (
    mark_startup_milestone,
)
from substitute.presentation.shell.restore_projection_controller import (
    restore_projection_controller_for,
)
from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info
from substitute.shared.startup_trace import trace_mark
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)

_EDITOR_TWO_COLUMN_WIDTH = 832
_LOGGER = get_logger("presentation.shell.shell_layout_controller")


class ShellLayoutController:
    """Own shell layout mutations that must touch live Qt widgets."""

    def __init__(self, shell: Any) -> None:
        """Store the shell host whose widgets are mutated by route changes."""

        self._shell = shell

    def set_cube_stack_material_region_enabled(self, enabled: bool) -> None:
        """Toggle whether the material surface cuts out the cube stack region."""

        surface = getattr(self._shell, "workspace_body_material_surface", None)
        set_region_widget = getattr(surface, "set_cube_stack_region_widget", None)
        if not callable(set_region_widget):
            return
        cube_stack_container = getattr(self._shell, "cube_stack_container", None)
        set_region_widget(cube_stack_container if enabled else None)

    def set_cube_stack_mode_button_enabled(self, enabled: bool) -> None:
        """Enable the workflow-only cube stack mode button for workflow routes."""

        button = getattr(self._shell, "cubeStackModeButton", None)
        set_enabled = getattr(button, "setEnabled", None)
        if callable(set_enabled):
            set_enabled(enabled)

    def set_orb_action_cluster_visible(self, visible: bool) -> None:
        """Show workflow-only under-orb actions for workflow routes."""

        if not visible:
            self._close_override_menu_if_open()

        cluster = getattr(self._shell, "orbActionCluster", None)
        set_visible = getattr(cluster, "setVisible", None)
        if callable(set_visible):
            set_visible(visible)

    def set_settings_toolbar_search_visible(self, visible: bool) -> None:
        """Show Settings search in shell chrome only while Settings is active."""

        search_box = getattr(self._shell, "settingsToolbarSearchBox", None)
        set_visible = getattr(search_box, "setVisible", None)
        if callable(set_visible):
            set_visible(visible)
            return

        show = getattr(search_box, "show", None)
        hide = getattr(search_box, "hide", None)
        if visible and callable(show):
            show()
        elif not visible and callable(hide):
            hide()

    def set_workflow_override_toolbar_visible(self, visible: bool) -> None:
        """Hide workflow override toolbar controls outside workflow routes."""

        if visible:
            return
        manager = getattr(self._shell, "active_override_manager", None)
        clear_controls = getattr(manager, "clear_toolbar_override_controls", None)
        if callable(clear_controls):
            clear_controls()

    def set_app_orb_workflow_file_actions_enabled(self, enabled: bool) -> None:
        """Toggle app-orb workflow file commands for the current shell route."""

        app_orb_menu = getattr(self._shell, "appOrbMenuButton", None)
        set_enabled = getattr(app_orb_menu, "set_workflow_file_actions_enabled", None)
        if callable(set_enabled):
            set_enabled(enabled)

    def initial_left_workspace_width(self) -> int:
        """Return the startup width that preserves the editor's two-column layout."""

        width = int(self._shell.cube_stack_container.width()) + _EDITOR_TWO_COLUMN_WIDTH
        self.log_editor_width_trace(
            "computed initial left workspace width",
            initial_left_workspace_width=width,
            editor_two_column_width=_EDITOR_TWO_COLUMN_WIDTH,
        )
        return width

    def current_main_splitter_sizes(self) -> tuple[int, ...]:
        """Return the live workflow/canvas splitter sizes as plain integers."""

        splitter = getattr(self._shell, "splitter", None)
        sizes = getattr(splitter, "sizes", None)
        if not callable(sizes):
            self.log_editor_width_trace("current main splitter sizes unavailable")
            return ()
        resolved_sizes = tuple(int(size) for size in sizes())
        self.log_editor_width_trace(
            "read current main splitter sizes",
            resolved_sizes=resolved_sizes,
        )
        return resolved_sizes

    def remember_workflow_splitter_sizes(self, sizes: Sequence[int]) -> None:
        """Store the durable workflow splitter sizes when they are restorable."""

        normalized_sizes = tuple(int(size) for size in sizes)
        self.log_editor_width_trace(
            "remember workflow splitter sizes requested",
            requested_sizes=normalized_sizes,
        )
        if len(normalized_sizes) < 2:
            self.log_editor_width_trace(
                "remember workflow splitter sizes rejected",
                requested_sizes=normalized_sizes,
                rejection_reason="fewer than two sizes",
            )
            return
        self._shell._remembered_workflow_splitter_sizes = normalized_sizes
        self.log_editor_width_trace(
            "remembered workflow splitter sizes",
            remembered_sizes=normalized_sizes,
        )

    def workflow_splitter_sizes_for_snapshot(self) -> tuple[int, ...]:
        """Return durable workflow splitter sizes for session capture."""

        remembered_sizes = tuple(
            getattr(self._shell, "_remembered_workflow_splitter_sizes", ())
        )
        if remembered_sizes:
            self.log_editor_width_trace(
                "snapshot workflow splitter sizes using remembered sizes",
                snapshot_splitter_sizes=remembered_sizes,
            )
            return remembered_sizes
        live_sizes = self.current_main_splitter_sizes()
        self.log_editor_width_trace(
            "snapshot workflow splitter sizes using live sizes",
            snapshot_splitter_sizes=live_sizes,
        )
        return live_sizes

    def apply_workflow_splitter_sizes(self, sizes: Sequence[int]) -> None:
        """Apply and remember durable workflow splitter sizes on the live splitter."""

        normalized_sizes = tuple(int(size) for size in sizes)
        self.log_editor_width_trace(
            "apply workflow splitter sizes requested",
            requested_sizes=normalized_sizes,
        )
        if len(normalized_sizes) < 2:
            self.log_editor_width_trace(
                "apply workflow splitter sizes rejected",
                requested_sizes=normalized_sizes,
                rejection_reason="fewer than two sizes",
            )
            return
        splitter = getattr(self._shell, "splitter", None)
        set_sizes = getattr(splitter, "setSizes", None)
        if callable(set_sizes):
            set_sizes(list(normalized_sizes))
            self.log_editor_width_trace(
                "applied workflow splitter sizes to live splitter",
                applied_sizes=normalized_sizes,
            )
        else:
            self.log_editor_width_trace(
                "live splitter setSizes unavailable during apply",
                requested_sizes=normalized_sizes,
            )
        self.remember_workflow_splitter_sizes(normalized_sizes)

    def can_apply_startup_default_splitter_layout(self) -> bool:
        """Return whether the shell still needs its first default splitter layout."""

        restored_applied = getattr(self._shell, "_restored_shell_layout_applied", False)
        remembered_sizes = tuple(
            getattr(self._shell, "_remembered_workflow_splitter_sizes", ())
        )
        can_apply = not restored_applied and not bool(remembered_sizes)
        self.log_editor_width_trace(
            "evaluated startup default splitter eligibility",
            can_apply=can_apply,
            restored_shell_layout_applied=restored_applied,
            remembered_workflow_splitter_sizes=remembered_sizes,
        )
        if restored_applied:
            return False
        return not bool(remembered_sizes)

    def apply_startup_default_splitter_layout(self) -> None:
        """Apply the initial splitter layout only before restore owns layout."""

        trace_mark(
            "main_window.apply_startup_default_splitter_layout.start",
            restored_shell_layout_applied=getattr(
                self._shell,
                "_restored_shell_layout_applied",
                False,
            ),
            remembered_workflow_splitter_sizes=tuple(
                getattr(self._shell, "_remembered_workflow_splitter_sizes", ())
            ),
            width=self._shell.width(),
        )
        if not self.can_apply_startup_default_splitter_layout():
            trace_mark(
                "main_window.apply_startup_default_splitter_layout.skip",
                reason="restore_or_remembered_layout_present",
            )
            self.log_editor_width_trace("skipped startup default splitter layout")
            log_info(
                _LOGGER,
                "mainwindow skipped startup default splitter layout",
                restored_shell_layout_applied=getattr(
                    self._shell,
                    "_restored_shell_layout_applied",
                    False,
                ),
                remembered_workflow_splitter_sizes=tuple(
                    getattr(self._shell, "_remembered_workflow_splitter_sizes", ())
                ),
                active_route=getattr(self._shell, "_active_workspace_route", ""),
            )
            return
        left_width = self.initial_left_workspace_width()
        default_sizes = (left_width, max(100, self._shell.width() - left_width))
        self.log_editor_width_trace(
            "applying startup default splitter layout",
            default_sizes=default_sizes,
        )
        self.apply_workflow_splitter_sizes(default_sizes)
        self.log_editor_width_trace(
            "applied startup default splitter layout",
            default_sizes=default_sizes,
        )
        log_info(
            _LOGGER,
            "mainwindow applied startup default splitter layout",
            restored_shell_layout_applied=getattr(
                self._shell,
                "_restored_shell_layout_applied",
                False,
            ),
            remembered_workflow_splitter_sizes=tuple(
                getattr(self._shell, "_remembered_workflow_splitter_sizes", ())
            ),
            active_route=getattr(self._shell, "_active_workspace_route", ""),
            applied_sizes=default_sizes,
        )
        trace_mark(
            "main_window.apply_startup_default_splitter_layout.end",
            default_sizes=default_sizes,
        )

    def handle_main_splitter_moved(self, position: int, index: int) -> None:
        """Persist user-owned workflow splitter movement."""

        self.log_editor_width_trace(
            "main splitter moved",
            splitter_position=position,
            splitter_index=index,
        )
        self._position_search_box()
        if getattr(self._shell, "_active_workspace_route", None) != (
            SETTINGS_WORKSPACE_ROUTE
        ):
            self.remember_workflow_splitter_sizes(self.current_main_splitter_sizes())
        else:
            self.log_editor_width_trace(
                "ignored main splitter move for durable width while settings active",
                splitter_position=position,
                splitter_index=index,
            )
        self._shell.request_session_autosave()
        self.log_editor_width_trace("requested autosave after main splitter move")

    def handle_editor_output_splitter_moved(self, position: int, index: int) -> None:
        """Trace and persist editor/output splitter movement."""

        self.log_editor_width_trace(
            "editor output splitter moved",
            splitter_position=position,
            splitter_index=index,
        )
        self._shell.request_session_autosave()
        self.log_editor_width_trace(
            "requested autosave after editor output splitter move",
        )

    def toggle_canvas_tabs(self, show: bool) -> None:
        """Show or hide canvas tabs and request the resulting shell width."""

        self.log_editor_width_trace(
            "toggle canvas tabs requested",
            show_canvas_tabs=show,
        )
        canvas_width = self._shell.canvas_tabs.sizeHint().width()
        active_panel = getattr(self._shell, "active_editor_panel", None)
        if callable(active_panel):
            active_panel = active_panel()
        if active_panel is None:
            active_panel = getattr(self._shell, "editor_panel", None)

        active_stack = getattr(self._shell, "active_cube_stack", None)
        if callable(active_stack):
            active_stack = active_stack()
        if active_stack is None:
            active_stack = getattr(self._shell, "cube_stack", None)
        if active_panel is None or active_stack is None:
            self.log_editor_width_trace(
                "toggle canvas tabs skipped missing active surfaces",
                show_canvas_tabs=show,
                active_panel_present=active_panel is not None,
                active_stack_present=active_stack is not None,
            )
            return
        base_width = active_panel.width() + active_stack.width()

        if show:
            if self._shell.splitter.indexOf(self._shell.canvas_tabs_container) == -1:
                details_widget = getattr(
                    self._shell,
                    "editor_output_container",
                    active_panel,
                )
                details_index = self._shell.splitter.indexOf(details_widget)
                self._shell.splitter.insertWidget(
                    details_index + 1,
                    self._shell.canvas_tabs_container,
                )
            target_width = base_width + canvas_width
            self._shell.resize_requested.emit(target_width)
            self.log_editor_width_trace(
                "toggle canvas tabs emitted show resize",
                target_width=target_width,
                base_width=base_width,
                canvas_width=canvas_width,
            )
        else:
            index = self._shell.splitter.indexOf(self._shell.canvas_tabs_container)
            if index != -1:
                self._shell.canvas_tabs_container.setParent(None)
            self._shell.resize_requested.emit(base_width)
            self.log_editor_width_trace(
                "toggle canvas tabs emitted hide resize",
                target_width=base_width,
                base_width=base_width,
                canvas_width=canvas_width,
            )
        self._position_search_box()

    def apply_restored_cube_stack_compact(self, compact: bool) -> None:
        """Restore cube-stack mode width without transferring splitter width."""

        new_width = CUBE_STACK_COMPACT_WIDTH if compact else CUBE_STACK_EXPANDED_WIDTH
        self.set_cube_stack_compact_state(compact)
        self.set_workflow_cube_stacks_compact(compact)
        cube_stack_container = getattr(self._shell, "cube_stack_container", None)
        set_fixed_width = getattr(cube_stack_container, "setFixedWidth", None)
        if callable(set_fixed_width):
            set_fixed_width(new_width)
        self.set_cube_stack_material_progress(1.0 if compact else 0.0)
        self.sync_cube_stack_mode_button(compact)
        self.log_editor_width_trace(
            "applied restored cube stack compact state",
            compact=compact,
            restored_cube_stack_width=new_width,
        )

    def set_cube_stack_compact(
        self,
        compact: bool,
        *,
        on_complete: Callable[[], None] | None = None,
        manual: bool = True,
    ) -> None:
        """Toggle cube stack compact mode while preserving editor width."""

        new_width = CUBE_STACK_COMPACT_WIDTH if compact else CUBE_STACK_EXPANDED_WIDTH
        if manual:
            workspace_cube_stack_actions = getattr(
                self._shell, "workspace_cube_stack_actions", None
            )
            on_manual_compact = getattr(
                workspace_cube_stack_actions,
                "on_cube_stack_compact_mode_manually_requested",
                None,
            )
            if callable(on_manual_compact):
                on_manual_compact(compact)
        self.set_cube_stack_compact_state(compact)
        self.log_editor_width_trace(
            "set cube stack compact requested",
            compact=compact,
            target_cube_stack_width=new_width,
        )
        if getattr(self._shell, "_active_workspace_route", None) == (
            SETTINGS_WORKSPACE_ROUTE
        ):
            self.set_workflow_cube_stacks_compact(compact)
            self._shell.cube_stack_container.setFixedWidth(new_width)
            self.set_cube_stack_material_progress(1.0 if compact else 0.0)
            self.sync_cube_stack_mode_button(compact)
            self._position_search_box()
            request_autosave = getattr(self._shell, "request_session_autosave", None)
            if callable(request_autosave):
                request_autosave()
            self.log_editor_width_trace(
                "completed settings route cube stack compact toggle",
                compact=compact,
            )
            if on_complete is not None:
                on_complete()
            return

        transition = getattr(self._shell, "_cube_stack_mode_transition", None)
        if transition is not None:
            self.log_editor_width_trace(
                "delegating cube stack compact toggle to transition",
                compact=compact,
            )
            transition_finished = getattr(transition, "transitionFinished", None)
            connect = getattr(transition_finished, "connect", None)
            if on_complete is not None and callable(connect):

                def _after_finished(finished_compact: bool) -> None:
                    """Run one compact-toggle callback after the target transition."""

                    if finished_compact != compact:
                        return
                    disconnect = getattr(transition_finished, "disconnect", None)
                    if callable(disconnect):
                        try:
                            disconnect(_after_finished)
                        except (RuntimeError, TypeError):
                            pass
                    on_complete()

                connect(_after_finished)
            transition.transition_to(compact)
            if on_complete is not None and not callable(connect):
                on_complete()
        else:
            old_width = self._shell.cube_stack_container.width()
            self.set_workflow_cube_stacks_compact(compact)
            self._shell.cube_stack_container.setFixedWidth(new_width)
            self.log_editor_width_trace(
                "applying cube stack compact toggle without transition",
                compact=compact,
                old_cube_stack_width=old_width,
                new_cube_stack_width=new_width,
            )
            self.transfer_cube_stack_width_to_canvas(old_width, new_width)
            self.set_cube_stack_material_progress(1.0 if compact else 0.0)
            if on_complete is not None:
                on_complete()
        self.sync_cube_stack_mode_button(compact)
        self._position_search_box()
        request_autosave = getattr(self._shell, "request_session_autosave", None)
        if callable(request_autosave):
            request_autosave()
        self.log_editor_width_trace(
            "completed workflow route cube stack compact toggle",
            compact=compact,
        )

    def set_workflow_cube_stacks_compact(self, compact: bool) -> None:
        """Apply immediate compact state to all workflow-owned cube stacks."""

        self.set_cube_stack_compact_state(compact)
        for cube_stack in getattr(self._shell, "cube_stacks", {}).values():
            self.apply_current_cube_stack_mode_to_stack(cube_stack)

    def set_cube_stack_material_progress(self, compact_progress: float) -> None:
        """Apply compact transition progress to the cube-stack material wash."""

        clamped_progress = max(0.0, min(1.0, float(compact_progress)))
        surface = getattr(self._shell, "workspace_body_material_surface", None)
        set_opacity = getattr(surface, "set_cube_stack_wash_opacity", None)
        if callable(set_opacity):
            set_opacity(1.0 - clamped_progress)

    def current_cube_stack_compact(self) -> bool:
        """Return the shell-owned cube stack compact mode."""

        return bool(getattr(self._shell, "_cube_stack_compact", False))

    def set_cube_stack_compact_state(self, compact: bool) -> None:
        """Store the shell-owned cube stack compact mode."""

        self._shell._cube_stack_compact = compact

    def apply_current_cube_stack_mode_to_stack(self, cube_stack: object) -> None:
        """Apply shell-owned cube stack mode to one stack widget."""

        set_compact = getattr(cube_stack, "setCompact", None)
        if callable(set_compact):
            set_compact(self.current_cube_stack_compact())

    def transfer_cube_stack_width_to_canvas(
        self,
        old_width: int,
        new_width: int,
    ) -> None:
        """Move cube-stack width delta between details and canvas splitter panes."""

        delta = old_width - new_width
        self.log_editor_width_trace(
            "transfer cube stack width to canvas requested",
            old_cube_stack_width=old_width,
            new_cube_stack_width=new_width,
            width_delta=delta,
        )
        if delta == 0:
            self.log_editor_width_trace(
                "transfer cube stack width skipped zero delta",
            )
            return

        splitter = getattr(self._shell, "splitter", None)
        if splitter is None:
            self.log_editor_width_trace(
                "transfer cube stack width skipped missing splitter",
            )
            return
        details_widget = getattr(self._shell, "editor_output_container", None)
        canvas_widget = getattr(self._shell, "canvas_tabs_container", None)
        if details_widget is None or canvas_widget is None:
            self.log_editor_width_trace(
                "transfer cube stack width skipped missing widgets",
                details_widget_present=details_widget is not None,
                canvas_widget_present=canvas_widget is not None,
            )
            return
        details_index = splitter.indexOf(details_widget)
        canvas_index = splitter.indexOf(canvas_widget)
        if details_index < 0 or canvas_index < 0:
            self.log_editor_width_trace(
                "transfer cube stack width skipped widget not in splitter",
                details_index=details_index,
                canvas_index=canvas_index,
            )
            return

        sizes = list(splitter.sizes())
        max_index = max(details_index, canvas_index)
        if len(sizes) <= max_index:
            self.log_editor_width_trace(
                "transfer cube stack width skipped sizes too short",
                sizes=tuple(sizes),
                max_index=max_index,
            )
            return

        old_sizes = tuple(sizes)
        sizes[details_index] = max(1, sizes[details_index] - delta)
        sizes[canvas_index] = max(100, sizes[canvas_index] + delta)
        splitter.setSizes(sizes)
        self.remember_workflow_splitter_sizes(sizes)
        self.log_editor_width_trace(
            "transferred cube stack width to canvas",
            old_splitter_sizes=old_sizes,
            new_splitter_sizes=tuple(sizes),
            details_index=details_index,
            canvas_index=canvas_index,
        )

    def sync_cube_stack_mode_button(self, compact: bool) -> None:
        """Reflect cube stack mode in the toolbar button."""

        button = getattr(self._shell, "cubeStackModeButton", None)
        if button is None:
            return
        set_checked = getattr(button, "setChecked", None)
        block_signals = getattr(button, "blockSignals", None)
        if callable(set_checked):
            previous_blocked: object = False
            if callable(block_signals):
                previous_blocked = block_signals(True)
            try:
                set_checked(compact)
            finally:
                if callable(block_signals):
                    block_signals(bool(previous_blocked))
        set_icon = getattr(button, "setIcon", None)
        if callable(set_icon):
            set_icon(
                AppIcon.PANEL_LEFT_20_REGULAR
                if compact
                else AppIcon.PANEL_LEFT_20_FILLED
            )
        button.setToolTip("Expand cube stack" if compact else "Collapse cube stack")

    def current_generation_queue_panel_visible(self) -> bool:
        """Return shell-owned target visibility for the full queue panel."""

        if hasattr(self._shell, "_generation_queue_panel_visible"):
            return bool(getattr(self._shell, "_generation_queue_panel_visible"))
        side_panel_host = getattr(self._shell, "sidePanelHost", None)
        is_visible = getattr(side_panel_host, "is_queue_panel_visible", None)
        return bool(is_visible()) if callable(is_visible) else False

    def set_generation_queue_panel_visible_state(self, visible: bool) -> None:
        """Store shell-owned target visibility for the full queue panel."""

        self._shell._generation_queue_panel_visible = visible

    def apply_restored_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Apply restorable shell layout facts after workspace widgets exist."""

        trace_mark(
            "main_window.apply_restored_shell_layout.start",
            shell_layout_present=snapshot is not None,
        )
        log_info(
            _LOGGER,
            "mainwindow apply restored shell layout",
            snapshot_present=snapshot is not None,
            active_route=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_id=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
        )
        self.log_editor_width_trace(
            "apply restored shell layout requested",
            snapshot_present=snapshot is not None,
            snapshot_main_splitter_sizes=tuple(snapshot.main_splitter_sizes)
            if snapshot is not None
            else (),
            snapshot_editor_output_splitter_sizes=tuple(
                snapshot.editor_output_splitter_sizes
            )
            if snapshot is not None
            else (),
            snapshot_cube_stack_compact=snapshot.cube_stack_compact
            if snapshot is not None
            else None,
        )
        if snapshot is None:
            self._shell._shell_restore_lifecycle = "running"
            mark_startup_milestone(
                getattr(self._shell, "_startup_timer", None),
                "restore_lifecycle_running",
            )
            self._maybe_capture_restore_projection_cache()
            trace_mark(
                "main_window.apply_restored_shell_layout.end",
                shell_layout_present=False,
            )
            return
        self._shell._restored_shell_layout_applied = True
        self._shell._shell_restore_lifecycle = "restoring"
        self._shell._pending_restored_shell_layout = snapshot
        self.log_editor_width_trace(
            "marked restored shell layout applied",
            snapshot_main_splitter_sizes=tuple(snapshot.main_splitter_sizes),
            snapshot_editor_output_splitter_sizes=tuple(
                snapshot.editor_output_splitter_sizes
            ),
        )
        window = self._shell.window()
        geometry = snapshot.geometry
        if geometry is not None:
            window.setGeometry(geometry.x, geometry.y, geometry.width, geometry.height)
            self.log_editor_width_trace(
                "applied restored shell geometry",
                geometry_x=geometry.x,
                geometry_y=geometry.y,
                geometry_width=geometry.width,
                geometry_height=geometry.height,
            )
        display_state = snapshot.window_display_state
        if snapshot.maximized and display_state == "normal":
            display_state = "maximized"
        self.apply_window_display_state(window, display_state)
        if display_state != "normal":
            self.log_editor_width_trace(
                "applied restored shell display state",
                window_display_state=display_state,
            )
        if isinstance(self._shell, QObject):
            self.apply_deferred_restored_shell_layout(
                snapshot,
                finalize=False,
            )
            trace_mark(
                "main_window.apply_deferred_restored_shell_layout.finalize",
                delay_ms=0,
            )
            QTimer.singleShot(
                0,
                lambda: self.apply_deferred_restored_shell_layout(
                    snapshot,
                    finalize=True,
                ),
            )
        else:
            self.apply_deferred_restored_shell_layout(
                snapshot,
                finalize=True,
            )
        log_info(
            _LOGGER,
            "mainwindow scheduled deferred shell layout restore",
            window_display_state=display_state,
            restored_main_splitter_sizes=tuple(snapshot.main_splitter_sizes),
            restored_editor_output_splitter_sizes=tuple(
                snapshot.editor_output_splitter_sizes
            ),
            active_route=getattr(self._shell, "_active_workspace_route", ""),
        )
        trace_mark(
            "main_window.apply_restored_shell_layout.end",
            shell_layout_present=True,
            window_display_state=display_state,
        )

    def apply_deferred_restored_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot,
        *,
        finalize: bool = True,
    ) -> None:
        """Apply canonical shell layout after geometry and widgets are available."""

        trace_mark(
            "main_window.apply_deferred_restored_shell_layout.start",
            finalize=finalize,
        )
        if getattr(self._shell, "_pending_restored_shell_layout", None) is not snapshot:
            trace_mark(
                "main_window.apply_deferred_restored_shell_layout.skip",
                reason="stale_snapshot",
                finalize=finalize,
            )
            return
        current_splitter_sizes = self.current_main_splitter_sizes()
        target_pane_count = len(current_splitter_sizes) or len(
            snapshot.main_splitter_sizes
        )
        available_width = self.safe_trace_width(getattr(self._shell, "splitter", None))
        if available_width is None or available_width <= 0:
            available_width = sum(current_splitter_sizes) or sum(
                snapshot.main_splitter_sizes
            )
        plan = build_shell_layout_restore_plan(
            snapshot,
            available_width=max(1, available_width),
            target_pane_count=max(2, target_pane_count),
            compact_cube_stack_width=CUBE_STACK_COMPACT_WIDTH,
            expanded_cube_stack_width=CUBE_STACK_EXPANDED_WIDTH,
        )
        self.apply_restored_cube_stack_compact(plan.cube_stack_compact)
        if plan.main_splitter_sizes:
            self.remember_workflow_splitter_sizes(plan.main_splitter_sizes)
            self.apply_workflow_splitter_sizes(plan.main_splitter_sizes)
        if plan.editor_output_splitter_sizes:
            self._shell.editor_output_splitter.setSizes(
                list(plan.editor_output_splitter_sizes)
            )
            self.log_editor_width_trace(
                "applied restored editor output splitter sizes",
                restored_editor_output_splitter_sizes=tuple(
                    plan.editor_output_splitter_sizes
                ),
            )
        self._set_comfy_output_panel_visible(snapshot.comfy_output_panel_visible)
        side_panel_width = plan.side_panel_width
        if side_panel_width is None:
            side_panel_width = snapshot.generation_queue_panel_width
        if side_panel_width is not None:
            self._shell.sidePanelHost.set_panel_width(side_panel_width)
        self.apply_restored_generation_queue_panel_visibility(
            snapshot.generation_queue_panel_visible or plan.side_panel_visible
        )
        if finalize:
            canvas_tabs = getattr(self._shell, "canvas_tabs", None)
            apply_canvas_layout = getattr(
                canvas_tabs,
                "apply_restored_canvas_layout",
                None,
            )
            if callable(apply_canvas_layout):
                apply_canvas_layout(snapshot.canvas_layout)
            self._shell._shell_restore_lifecycle = "running"
            self._shell._pending_restored_shell_layout = None
            mark_startup_milestone(
                getattr(self._shell, "_startup_timer", None),
                "restore_lifecycle_running",
            )
            trace_mark("main_window.restore_finalized.emit")
            self._shell.restore_finalized.emit()
            self._maybe_capture_restore_projection_cache()
        self.log_editor_width_trace(
            "applied deferred restored shell layout",
            restore_plan_main_splitter_sizes=tuple(plan.main_splitter_sizes),
            restore_plan_editor_output_splitter_sizes=tuple(
                plan.editor_output_splitter_sizes
            ),
            restore_plan_cube_stack_width=plan.cube_stack_width,
            restore_plan_side_panel_visible=plan.side_panel_visible,
            restore_plan_side_panel_width=plan.side_panel_width,
            restore_plan_used_legacy_splitter=plan.used_legacy_splitter,
            restore_plan_clamped_fields=tuple(plan.clamped_fields),
            restore_finalized=finalize,
        )
        log_info(
            _LOGGER,
            "mainwindow applied deferred shell layout restore",
            main_splitter_sizes=tuple(plan.main_splitter_sizes),
            editor_output_splitter_sizes=tuple(plan.editor_output_splitter_sizes),
            cube_stack_width=plan.cube_stack_width,
            side_panel_visible=plan.side_panel_visible,
            side_panel_width=plan.side_panel_width,
            used_legacy_splitter=plan.used_legacy_splitter,
            clamped_fields=tuple(plan.clamped_fields),
            restore_finalized=finalize,
            active_route=getattr(self._shell, "_active_workspace_route", ""),
        )
        trace_mark(
            "main_window.apply_deferred_restored_shell_layout.end",
            finalize=finalize,
            side_panel_width=side_panel_width,
            main_splitter_sizes=tuple(plan.main_splitter_sizes),
        )

    def apply_restored_generation_queue_panel_visibility(self, visible: bool) -> None:
        """Apply restore-owned queue panel visibility without animation or autosave."""

        self.set_generation_queue_panel_visible_state(visible)
        side_panel_host = getattr(self._shell, "sidePanelHost", None)
        set_visible = getattr(side_panel_host, "set_queue_panel_visible", None)
        if callable(set_visible):
            set_visible(visible)
        self._shell.generation_action_controller.apply_generation_action_availability()

    def capture_shell_layout_snapshot(self) -> ShellLayoutSnapshot | None:
        """Return restorable shell layout state with canonical stack width."""

        window = self._shell.window()
        geometry = window.geometry()
        main_splitter_sizes = self.workflow_splitter_sizes_for_snapshot()
        cube_stack_compact = self.current_cube_stack_compact()
        cube_stack_width = (
            CUBE_STACK_COMPACT_WIDTH
            if cube_stack_compact
            else CUBE_STACK_EXPANDED_WIDTH
        )
        editor_panel_width = self.editor_panel_width_for_snapshot(
            main_splitter_sizes=main_splitter_sizes,
            cube_stack_width=cube_stack_width,
        )
        canvas_panel_width = self.canvas_panel_width_for_snapshot(
            main_splitter_sizes=main_splitter_sizes,
        )
        side_panel_visible = self.current_generation_queue_panel_visible()
        side_panel_host = getattr(self._shell, "sidePanelHost", None)
        panel_width = getattr(side_panel_host, "panel_width", None)
        side_panel_width = int(panel_width()) if callable(panel_width) else None
        output_panel_height = (
            self.safe_widget_height(getattr(self._shell, "comfy_output_panel", None))
            if self._is_comfy_output_panel_visible()
            else None
        )
        canonical_layout = canonical_layout_from_measurements(
            LiveShellLayoutMeasurements(
                main_splitter_sizes=main_splitter_sizes,
                editor_output_splitter_sizes=tuple(
                    self._shell.editor_output_splitter.sizes()
                ),
                cube_stack_width=cube_stack_width,
                editor_panel_width=editor_panel_width,
                canvas_panel_width=canvas_panel_width,
                side_panel_visible=side_panel_visible,
                side_panel_width=side_panel_width,
                output_panel_height=output_panel_height,
            )
        )
        window_display_state = self.window_display_state(window)
        canvas_layout_snapshot = None
        canvas_snapshot = getattr(
            getattr(self._shell, "canvas_tabs", None),
            "canvas_layout_snapshot",
            None,
        )
        if callable(canvas_snapshot):
            canvas_layout_snapshot = canvas_snapshot()
        floating_canvas_windows = (
            tuple(canvas_layout_snapshot.floating_windows)
            if canvas_layout_snapshot is not None
            else ()
        )
        floating_canvas_labels = tuple(
            floating_window.label for floating_window in floating_canvas_windows
        )
        output_generation_controls_revealed = any(
            floating_window.label == "Output"
            and floating_window.output_generation_controls_revealed
            for floating_window in floating_canvas_windows
        )
        editor_output_splitter_sizes = tuple(self._shell.editor_output_splitter.sizes())
        log_debug(
            _LOGGER,
            "mainwindow shell layout snapshot captured",
            main_splitter_sizes=main_splitter_sizes,
            editor_output_splitter_sizes=editor_output_splitter_sizes,
            cube_stack_width=cube_stack_width,
            editor_panel_width=canonical_layout.editor_panel_width,
            canvas_panel_width=canonical_layout.canvas_panel_width,
            cube_stack_compact=cube_stack_compact,
            active_route=getattr(self._shell, "_active_workspace_route", ""),
            active_workflow_id=getattr(
                getattr(self._shell, "workflow_session_service", None),
                "active_workflow_id",
                "",
            ),
            window_display_state=window_display_state,
            side_panel_visible=canonical_layout.side_panel_visible,
            side_panel_width=canonical_layout.side_panel_width,
            output_panel_height=canonical_layout.output_panel_height,
            floating_canvas_count=len(floating_canvas_windows),
            floating_canvas_labels=floating_canvas_labels,
            output_generation_controls_revealed=(output_generation_controls_revealed),
        )
        self.log_editor_width_trace(
            "shell layout snapshot captured",
            snapshot_main_splitter_sizes=main_splitter_sizes,
            snapshot_editor_output_splitter_sizes=editor_output_splitter_sizes,
            snapshot_cube_stack_width=cube_stack_width,
            snapshot_cube_stack_compact=cube_stack_compact,
            snapshot_editor_panel_width=canonical_layout.editor_panel_width,
            snapshot_canvas_panel_width=canonical_layout.canvas_panel_width,
            snapshot_comfy_output_panel_visible=(self._is_comfy_output_panel_visible()),
            snapshot_output_panel_height=canonical_layout.output_panel_height,
            snapshot_side_panel_visible=canonical_layout.side_panel_visible,
            snapshot_side_panel_width=canonical_layout.side_panel_width,
            snapshot_generation_queue_panel_visible=(
                self.current_generation_queue_panel_visible()
            ),
            snapshot_generation_queue_panel_width=side_panel_width,
            snapshot_floating_canvas_count=len(floating_canvas_windows),
            snapshot_floating_canvas_labels=floating_canvas_labels,
            snapshot_output_generation_controls_revealed=(
                output_generation_controls_revealed
            ),
        )
        return ShellLayoutSnapshot(
            geometry=WindowGeometrySnapshot(
                x=geometry.x(),
                y=geometry.y(),
                width=geometry.width(),
                height=geometry.height(),
            ),
            window_display_state=window_display_state,
            maximized=window.isMaximized(),
            main_splitter_sizes=main_splitter_sizes,
            editor_output_splitter_sizes=editor_output_splitter_sizes,
            cube_stack_width=canonical_layout.cube_stack_width,
            editor_panel_width=canonical_layout.editor_panel_width,
            canvas_panel_width=canonical_layout.canvas_panel_width,
            cube_stack_compact=cube_stack_compact,
            comfy_output_panel_visible=self._is_comfy_output_panel_visible(),
            output_panel_height=canonical_layout.output_panel_height,
            side_panel_visible=canonical_layout.side_panel_visible,
            side_panel_width=canonical_layout.side_panel_width,
            generation_queue_panel_visible=(
                self.current_generation_queue_panel_visible()
            ),
            generation_queue_panel_width=side_panel_width,
            canvas_layout=canvas_layout_snapshot,
        )

    def editor_panel_width_for_snapshot(
        self,
        *,
        main_splitter_sizes: tuple[int, ...],
        cube_stack_width: int,
    ) -> int | None:
        """Return the durable editor-panel width for shell snapshot capture."""

        active_editor_panel = getattr(self._shell, "active_editor_panel", None)
        if callable(active_editor_panel):
            try:
                active_editor_panel = active_editor_panel()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                active_editor_panel = None
        width = self.safe_trace_width(active_editor_panel)
        if width is not None:
            return width
        if main_splitter_sizes:
            return max(0, int(main_splitter_sizes[0]) - cube_stack_width)
        return None

    def canvas_panel_width_for_snapshot(
        self,
        *,
        main_splitter_sizes: tuple[int, ...],
    ) -> int | None:
        """Return the durable canvas width for shell snapshot capture."""

        if len(main_splitter_sizes) >= 2:
            return max(0, int(main_splitter_sizes[1]))
        return self.safe_trace_width(
            getattr(self._shell, "canvas_tabs_container", None)
        )

    def log_editor_width_trace(self, event: str, **context: object) -> None:
        """Log one shell layout trace point with live layout facts."""

        emit_editor_width_trace(_LOGGER, self._shell, event, **context)

    @staticmethod
    def safe_trace_width(widget: object | None) -> int | None:
        """Return a widget width for shell layout logging and capture."""

        return safe_trace_width(widget)

    @staticmethod
    def safe_widget_height(widget: object | None) -> int | None:
        """Return a widget height for shell layout capture."""

        height = getattr(widget, "height", None)
        if not callable(height):
            return None
        try:
            return int(height())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None

    @staticmethod
    def safe_trace_splitter_sizes(splitter: object | None) -> tuple[int, ...]:
        """Return splitter sizes for shell layout logging."""

        return safe_trace_splitter_sizes(splitter)

    @staticmethod
    def window_display_state(window: object) -> str:
        """Return a stable display-state label for a shell window."""

        is_full_screen = getattr(window, "isFullScreen", None)
        if callable(is_full_screen) and is_full_screen():
            return "fullscreen"
        is_maximized = getattr(window, "isMaximized", None)
        if callable(is_maximized) and is_maximized():
            return "maximized"
        return "normal"

    @staticmethod
    def apply_window_display_state(window: object, display_state: str) -> None:
        """Apply a supported persisted display state to the shell window."""

        if display_state == "fullscreen":
            show_full_screen = getattr(window, "showFullScreen", None)
            if callable(show_full_screen):
                show_full_screen()
            return
        if display_state == "maximized":
            show_maximized = getattr(window, "showMaximized", None)
            if callable(show_maximized):
                show_maximized()
            return
        show_normal = getattr(window, "showNormal", None)
        if callable(show_normal):
            show_normal()

    def _maybe_capture_restore_projection_cache(self) -> None:
        """Request restore projection cache capture through its owning controller."""

        restore_projection_controller_for(
            self._shell
        ).maybe_capture_restore_projection_cache()

    def _position_search_box(self) -> None:
        """Ask the search overlay owner to refresh floating search geometry."""

        controller = getattr(self._shell, "search_overlay_controller", None)
        position_search_box = getattr(controller, "position_search_box", None)
        if callable(position_search_box):
            position_search_box()
            return
        search_overlay_controller_for(self._shell).position_search_box()

    def _is_comfy_output_panel_visible(self) -> bool:
        """Return Comfy output visibility through its owning controller."""

        actions = getattr(self._shell, "comfy_runtime_actions", None)
        is_visible = getattr(actions, "is_comfy_output_panel_visible", None)
        if callable(is_visible):
            return bool(is_visible())
        return comfy_runtime_actions_for(self._shell).is_comfy_output_panel_visible()

    def _set_comfy_output_panel_visible(self, visible: bool) -> None:
        """Apply Comfy output visibility through its owning controller."""

        actions = getattr(self._shell, "comfy_runtime_actions", None)
        set_visible = getattr(actions, "set_comfy_output_panel_visible", None)
        if callable(set_visible):
            set_visible(visible)
            return
        comfy_runtime_actions_for(self._shell).set_comfy_output_panel_visible(visible)

    def _close_override_menu_if_open(self) -> None:
        """Close workflow override chrome before hiding its action cluster."""

        controller = getattr(
            getattr(self._shell, "override_dropdown_btn", None),
            "_menu_controller",
            None,
        )
        close_menu_if_open = getattr(controller, "close_menu_if_open", None)
        if callable(close_menu_if_open):
            close_menu_if_open()
