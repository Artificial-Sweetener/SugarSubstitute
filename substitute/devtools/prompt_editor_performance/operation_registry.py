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

"""Route prompt-editor performance scenarios to focused timing owners."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from substitute.presentation.editor.prompt_editor import PromptEditor

from .cache_operations import (
    time_diagnostic_cache_operations,
    time_fill_band_cache_operations,
    time_projection_paint_cache_operations,
)
from .editing_operations import (
    operation_key,
    time_cursor_move_operations,
    time_key_click,
    time_paste_operation,
    time_selection_change_operations,
)
from .metrics import Instrumentation
from .reorder_operations import (
    time_reorder_alt_arrow_operations,
    time_reorder_alt_drag_operations,
    time_reorder_drag_operations,
)
from .scenarios import Scenario
from .viewport_operations import (
    time_context_menu_open,
    time_focus_operations,
    time_hover_operations,
    time_resize_operations,
    time_scroll_operations,
)


def run_scenario_operations(
    *,
    app: QApplication,
    editor: PromptEditor,
    scenario: Scenario,
    instrumentation: Instrumentation,
    extra_counts: dict[str, int | float],
) -> list[float]:
    """Run the configured operation through its focused timing owner."""

    if scenario.operation in {"type", "autocomplete", "ghost_text"}:
        return [
            time_key_click(app, editor, character=character)
            for character in scenario.typed_text
        ]

    if scenario.operation in {"backspace", "delete", "enter"}:
        key = operation_key(scenario.operation)
        return [
            time_key_click(app, editor, key=key)
            for _ in range(scenario.operation_count or 1)
        ]

    if scenario.operation == "cursor_move":
        return time_cursor_move_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "selection_change":
        return time_selection_change_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation in {"paste", "paste_import"}:
        return [
            time_paste_operation(
                app,
                editor,
                clipboard_text=scenario.clipboard_text,
            )
        ]
    if scenario.operation == "projection_paint_cache":
        return time_projection_paint_cache_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation == "diagnostic_cache":
        return time_diagnostic_cache_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation == "fill_band_cache":
        return time_fill_band_cache_operations(
            app,
            editor,
            scenario.operation_count or 1,
        )
    if scenario.operation == "scroll":
        return time_scroll_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "resize":
        return time_resize_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "hover":
        return time_hover_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "focus":
        return time_focus_operations(app, editor, scenario.operation_count or 1)
    if scenario.operation == "context_menu":
        return [time_context_menu_open(app, editor)]
    if scenario.operation == "reorder_drag":
        return time_reorder_drag_operations(
            app,
            editor,
            scenario.operation_count or 1,
            instrumentation,
        )
    if scenario.operation == "reorder_alt_drag":
        return time_reorder_alt_drag_operations(
            app,
            editor,
            scenario.operation_count or 1,
            mode=scenario.reorder_drag_mode,
            extra_counts=extra_counts,
        )
    if scenario.operation == "reorder_alt_arrow":
        return time_reorder_alt_arrow_operations(
            app,
            editor,
            scenario.reorder_keys,
            extra_counts=extra_counts,
        )
    raise ValueError(f"Unsupported performance operation: {scenario.operation}")


__all__ = ["run_scenario_operations"]
