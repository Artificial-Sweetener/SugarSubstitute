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

"""Restore and capture the persisted shell layout."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QObject, QTimer

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
from substitute.presentation.workflows.cube_stack_view import (
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_info
from substitute.shared.startup_trace import trace_mark

_LOGGER = get_logger("presentation.shell.shell_layout_restore_controller")


class ShellLayoutRestoreController:
    """Own shell layout restore and compatible snapshot capture."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose persisted layout is restored and captured."""

        self._shell = shell

    def apply_restored_cube_stack_compact(self, compact: bool) -> None:
        """Restore cube-stack mode width without transferring splitter width."""

        self._shell.cube_stack_presentation_controller.restore_preference(compact)

    def current_cube_stack_compact(self) -> bool:
        """Return the shell-owned cube stack compact mode."""

        preference = self._shell.cube_stack_presentation_controller.preference
        return bool(preference.value == "compact")

    def current_main_splitter_sizes(self) -> tuple[int, ...]:
        """Return live sizes through the durable workspace layout owner."""

        return tuple(
            int(size)
            for size in self._shell.workspace_layout_controller.current_main_splitter_sizes()
        )

    def remember_workflow_splitter_sizes(self, sizes: Sequence[int]) -> None:
        """Remember durable sizes through the workspace layout owner."""

        self._shell.workspace_layout_controller.remember_workflow_splitter_sizes(sizes)

    def workflow_splitter_sizes_for_snapshot(self) -> tuple[int, ...]:
        """Return canonical sizes through the workspace layout owner."""

        return tuple(
            int(size)
            for size in self._shell.workspace_layout_controller.workflow_splitter_sizes_for_snapshot()
        )

    def apply_workflow_splitter_sizes(self, sizes: Sequence[int]) -> None:
        """Apply durable sizes through the workspace layout owner."""

        self._shell.workspace_layout_controller.apply_workflow_splitter_sizes(sizes)

    def current_generation_queue_panel_visible(self) -> bool:
        """Return shell-owned target visibility for the full queue panel."""

        return bool(self._shell.generation_queue_controller.panel_visible)

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

        self._shell.generation_queue_controller.apply_panel_visibility(
            visible,
            request_autosave=False,
            animated=False,
        )

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
