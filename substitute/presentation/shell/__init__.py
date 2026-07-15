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

"""Expose shell presentation symbols via lazy imports."""

from __future__ import annotations

from typing import Any

__all__ = [
    "GenerationUiBindings",
    "MainWindow",
    "MainWindowDependencies",
    "SplashWindow",
    "WorkspaceController",
    "WorkspaceGenerationController",
]


def __getattr__(name: str) -> Any:
    """Load shell exports lazily to avoid importing heavy Qt modules eagerly."""
    if name == "MainWindow":
        from substitute.presentation.shell.main_window import MainWindow

        return MainWindow
    if name == "MainWindowDependencies":
        from substitute.presentation.shell.main_window_dependencies import (
            MainWindowDependencies,
        )

        return MainWindowDependencies
    if name == "SplashWindow":
        from substitute.presentation.shell.splash_window import SplashWindow

        return SplashWindow
    if name in {
        "GenerationUiBindings",
        "WorkspaceController",
        "WorkspaceGenerationController",
    }:
        from substitute.presentation.shell.workspace_controller import (
            WorkspaceController,
        )
        from substitute.presentation.shell.workspace_generation_controller import (
            GenerationUiBindings,
            WorkspaceGenerationController,
        )

        return {
            "GenerationUiBindings": GenerationUiBindings,
            "WorkspaceController": WorkspaceController,
            "WorkspaceGenerationController": WorkspaceGenerationController,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
