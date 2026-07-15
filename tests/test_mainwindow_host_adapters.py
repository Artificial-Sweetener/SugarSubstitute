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

"""Verify MainWindow host adapters stay thin and delegate to composed owners."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)


def test_active_surface_accessors_delegate_to_active_surface_controller() -> None:
    """MainWindow active-surface accessors should stay as host-bound adapters."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")

    assert "return self.shell_active_surface_controller.get_active_workflow()" in source
    assert "return self.shell_active_surface_controller.active_editor_panel()" in source
    assert "return self.shell_active_surface_controller.active_cube_stack()" in source
    assert (
        "return self.shell_active_surface_controller.active_override_manager()"
        in source
    )


def test_event_filter_delegates_to_shell_event_filter_controller() -> None:
    """MainWindow event filtering should stay behind the shell event-filter owner."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")
    start = source.index("    def eventFilter(")
    end = source.index("    def get_active_workflow(", start)
    method_source = source[start:end]

    assert (
        "self.shell_event_filter_controller.handle_event_filter_event(event)"
        in method_source
    )
    assert "if result is not None:" in method_source
    assert "return super().eventFilter(source, event)" in method_source
