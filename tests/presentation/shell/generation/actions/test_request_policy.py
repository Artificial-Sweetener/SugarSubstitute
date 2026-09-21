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

"""Tests for workspace generation action binding helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from substitute.presentation.shell.workspace_generation_action_adapter import (
    effective_generation_batch_count,
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


def test_effective_generation_batch_count_prefers_registry_and_clamps() -> None:
    """Titlebar registry batch count should win over legacy cluster values."""

    view = SimpleNamespace(
        generation_titlebar_control_registry=SimpleNamespace(
            effective_batch_count=lambda: 0
        ),
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 7),
    )

    assert effective_generation_batch_count(view) == 1


def test_effective_generation_batch_count_uses_legacy_cluster_fallback() -> None:
    """Legacy generation action cluster should supply batch count when needed."""

    view = SimpleNamespace(
        generationActionCluster=SimpleNamespace(effective_batch_count=lambda: 4)
    )

    assert effective_generation_batch_count(view) == 4
    assert effective_generation_batch_count(SimpleNamespace()) == 1
