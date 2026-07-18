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

"""Own durable workspace splitter layout and canvas participation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


from substitute.presentation.shell.shell_layout_trace import (
    log_editor_width_trace as emit_editor_width_trace,
    safe_trace_splitter_sizes,
    safe_trace_width,
)
from substitute.presentation.shell.search_overlay_controller import (
    search_overlay_controller_for,
)
from substitute.shared.logging.logger import get_logger, log_info
from substitute.shared.startup_trace import trace_mark
from substitute.presentation.workflows.workflow_tabs_view import (
    SETTINGS_WORKSPACE_ROUTE,
)

_EDITOR_TWO_COLUMN_WIDTH = 832
_LOGGER = get_logger("presentation.shell.workspace_layout_controller")


class WorkspaceLayoutController:
    """Own durable splitter layout, movement, and canvas participation."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose workspace splitter is coordinated."""

        self._shell = shell

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

        workspace_splitter = getattr(
            self._shell,
            "workspace_splitter_controller",
            None,
        )
        current_sizes = getattr(workspace_splitter, "current_sizes", None)
        if callable(current_sizes):
            return tuple(current_sizes())
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
        workspace_splitter = getattr(
            self._shell,
            "workspace_splitter_controller",
            None,
        )
        remember_sizes = getattr(workspace_splitter, "remember_sizes", None)
        if callable(remember_sizes):
            remember_sizes(normalized_sizes)
        self._shell._remembered_workflow_splitter_sizes = normalized_sizes
        self.log_editor_width_trace(
            "remembered workflow splitter sizes",
            remembered_sizes=normalized_sizes,
        )

    def workflow_splitter_sizes_for_snapshot(self) -> tuple[int, ...]:
        """Return durable workflow splitter sizes for session capture."""

        presentation = getattr(
            self._shell,
            "cube_stack_presentation_controller",
            None,
        )
        presentation_sizes = getattr(
            presentation,
            "splitter_sizes_for_snapshot",
            None,
        )
        if callable(presentation_sizes):
            return tuple(presentation_sizes())
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
        workspace_splitter = getattr(
            self._shell,
            "workspace_splitter_controller",
            None,
        )
        apply_durable_sizes = getattr(
            workspace_splitter,
            "apply_durable_sizes",
            None,
        )
        if callable(apply_durable_sizes):
            apply_durable_sizes(normalized_sizes)
            self._shell._remembered_workflow_splitter_sizes = normalized_sizes
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
            presentation = getattr(
                self._shell,
                "cube_stack_presentation_controller",
                None,
            )
            normalize = getattr(
                presentation,
                "normalize_current_splitter_geometry",
                None,
            )
            if callable(normalize):
                canonical_sizes = tuple(normalize())
                self._shell._remembered_workflow_splitter_sizes = canonical_sizes
            else:
                self.remember_workflow_splitter_sizes(
                    self.current_main_splitter_sizes()
                )
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

        if active_panel is None:
            self.log_editor_width_trace(
                "toggle canvas tabs skipped missing active editor",
                show_canvas_tabs=show,
            )
            return
        stack_width = int(self._shell.cube_stack_container.width())
        base_width = int(active_panel.width()) + stack_width

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

    def _position_search_box(self) -> None:
        """Ask the search overlay owner to refresh floating search geometry."""

        controller = getattr(self._shell, "search_overlay_controller", None)
        position_search_box = getattr(controller, "position_search_box", None)
        if callable(position_search_box):
            position_search_box()
            return
        search_overlay_controller_for(self._shell).position_search_box()
