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

"""Support workspace generation action binding helpers."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from substitute.presentation.shell.workspace_generation_controller import (
    GenerationUiBindings,
)


PROJECT_ROOT = Path(__file__).resolve().parents[5]
SOURCE_PATH = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "shell"
    / "workspace_generation_action_adapter.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.shell.workspace_controller",
)


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _dispatcher() -> SimpleNamespace:
    """Return distinct generation feedback callbacks."""

    return SimpleNamespace(
        on_run_started=lambda _event: None,
        on_progress=lambda _progress: None,
        on_model_load_progress=lambda _progress: None,
        on_preview=lambda _preview: None,
        on_output_image=lambda _output: None,
        on_failure=lambda _failure: None,
        on_timing=lambda _timing: None,
        on_completed=lambda _event: None,
    )


def _bindings() -> GenerationUiBindings:
    """Return inert generation bindings for action-intent tests."""

    return GenerationUiBindings(
        build_generation_request=lambda: cast(Any, None),
        randomize_seeds=lambda: None,
        on_progress=lambda _progress: None,
        on_model_load_progress=lambda _progress: None,
        on_preview=lambda _preview: None,
        on_output_image=lambda _output: None,
        on_failure=lambda _failure: None,
        on_timing=lambda _timing: None,
        on_completed=lambda _event: None,
        refresh_generation_actions=lambda: None,
    )
