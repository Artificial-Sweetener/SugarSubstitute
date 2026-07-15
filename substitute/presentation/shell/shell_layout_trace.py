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

"""Build and emit shell layout trace records from live presentation widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.shared.logging.logger import log_debug


def log_editor_width_trace(
    logger: Any,
    shell: object,
    event: str,
    **context: object,
) -> None:
    """Log one shell layout trace point with live layout facts."""

    workflow_session_service = getattr(shell, "workflow_session_service", None)
    splitter = getattr(shell, "splitter", None)
    editor_output_splitter = getattr(shell, "editor_output_splitter", None)
    active_editor_panel = _active_editor_panel(shell)
    trace_context: dict[str, object] = {
        "trace_event": event,
        "active_route": getattr(shell, "_active_workspace_route", ""),
        "active_workflow_id": getattr(
            workflow_session_service,
            "active_workflow_id",
            "",
        ),
        "restored_shell_layout_applied": getattr(
            shell,
            "_restored_shell_layout_applied",
            None,
        ),
        "remembered_workflow_splitter_sizes": tuple(
            getattr(shell, "_remembered_workflow_splitter_sizes", ())
        ),
        "live_main_splitter_sizes": safe_trace_splitter_sizes(splitter),
        "live_editor_output_splitter_sizes": safe_trace_splitter_sizes(
            editor_output_splitter
        ),
        "cube_stack_container_width": safe_trace_width(
            getattr(shell, "cube_stack_container", None)
        ),
        "editor_output_container_width": safe_trace_width(
            getattr(shell, "editor_output_container", None)
        ),
        "canvas_tabs_container_width": safe_trace_width(
            getattr(shell, "canvas_tabs_container", None)
        ),
        "active_editor_panel_width": safe_trace_width(active_editor_panel),
        "main_window_width": safe_trace_width(shell),
        "shell_window_width": safe_trace_width(_window_object(shell)),
    }
    trace_context.update(context)
    log_debug(
        logger,
        "mainwindow shell layout trace",
        **trace_context,
    )


def safe_trace_width(widget: object | None) -> int | None:
    """Return a widget width for shell layout logging and capture."""

    width = getattr(widget, "width", None)
    if not callable(width):
        return None
    try:
        return int(width())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def safe_trace_splitter_sizes(splitter: object | None) -> tuple[int, ...]:
    """Return splitter sizes for shell layout logging."""

    sizes = getattr(splitter, "sizes", None)
    if not callable(sizes):
        return ()
    try:
        return tuple(int(size) for size in sizes())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ()


def _active_editor_panel(shell: object) -> object | None:
    """Return the active editor panel while tolerating torn-down widgets."""

    active_editor_panel = getattr(shell, "active_editor_panel", None)
    if not callable(active_editor_panel):
        return cast(object | None, active_editor_panel)
    try:
        return cast(Callable[[], object | None], active_editor_panel)()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _window_object(shell: object) -> object | None:
    """Return the shell window object while tolerating torn-down widgets."""

    window = getattr(shell, "window", None)
    if not callable(window):
        return None
    try:
        return cast(Callable[[], object | None], window)()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


__all__ = [
    "log_editor_width_trace",
    "safe_trace_splitter_sizes",
    "safe_trace_width",
]
