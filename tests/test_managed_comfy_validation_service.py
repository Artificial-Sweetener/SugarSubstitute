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

"""Tests for managed-local Comfy workspace validation helpers."""

from __future__ import annotations

from pathlib import Path

from substitute.infrastructure.comfy.managed_validation import (
    is_workspace_installed,
    is_workspace_launchable,
    workspace_main_path,
    workspace_nested_main_path,
    workspace_python_path,
)


def test_workspace_installed_requires_python_and_main(tmp_path: Path) -> None:
    """Managed workspace should require launchable runtime artifacts."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    workspace_main_path(tmp_path).write_text("main", encoding="utf-8")

    assert is_workspace_installed(tmp_path) is True
    assert is_workspace_launchable(tmp_path) is True


def test_workspace_validation_rejects_legacy_nested_layout(tmp_path: Path) -> None:
    """Legacy nested layouts should not count as installed canonical workspaces."""

    python_path = workspace_python_path(tmp_path)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.write_text("", encoding="utf-8")
    nested_main = workspace_nested_main_path(tmp_path)
    nested_main.parent.mkdir(parents=True, exist_ok=True)
    nested_main.write_text("nested", encoding="utf-8")

    assert is_workspace_installed(tmp_path) is False
    assert is_workspace_launchable(tmp_path) is False


def test_workspace_installed_fails_closed_when_any_artifact_is_missing(
    tmp_path: Path,
) -> None:
    """Managed workspace validation should fail closed for partial installs."""

    assert is_workspace_installed(tmp_path) is False
    assert is_workspace_launchable(tmp_path) is False
