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

"""Verify MainWindow delegates composition without presentation-library imports."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "main_window_composition.py"
)


def test_main_window_routes_dependency_capture_through_composition_module() -> None:
    """Require MainWindow to delegate dependency and controller composition."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")

    assert "def _capture_dependencies" not in source
    assert "capture_dependencies(self, dependencies)" in source
    assert "compose_shell_controllers(self)" in source
    assert "connect_shell_signals(" in source


def test_main_window_composition_does_not_import_qt() -> None:
    """Keep the composition owner independent from direct Qt imports."""

    source = COMPOSITION_SOURCE.read_text(encoding="utf-8")

    assert "PySide6" not in source
    assert "qfluentwidgets" not in source
