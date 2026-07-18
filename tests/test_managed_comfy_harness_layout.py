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

"""Verify portable managed-Comfy layout resolution for real harnesses."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.managed_comfy_harness_layout import ManagedComfyHarnessLayout


@pytest.mark.parametrize(
    ("platform_name", "python_relative"),
    (
        ("nt", Path(".venv") / "Scripts" / "python.exe"),
        ("posix", Path(".venv") / "bin" / "python"),
    ),
)
def test_layout_resolves_runtime_and_template_package_without_host_assumptions(
    tmp_path: Path,
    platform_name: str,
    python_relative: Path,
) -> None:
    """Managed harness paths should derive from the selected interpreter."""

    comfy_root = tmp_path / "comfyui"
    (comfy_root / "main.py").parent.mkdir(parents=True)
    (comfy_root / "main.py").touch()
    python_executable = comfy_root / python_relative
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    template_root = (
        comfy_root
        / ".venv"
        / "packages"
        / "comfyui_workflow_templates_media_image"
        / "templates"
    )
    template_root.mkdir(parents=True)

    layout = ManagedComfyHarnessLayout.resolve(
        tmp_path,
        platform_name=platform_name,
    )

    assert layout.python_executable == python_executable.resolve()
    assert layout.environment_root == (comfy_root / ".venv").resolve()
    assert layout.image_template_root() == template_root


def test_layout_rejects_ambiguous_template_packages(tmp_path: Path) -> None:
    """A harness should fail closed when package ownership is ambiguous."""

    comfy_root = tmp_path / "comfyui"
    (comfy_root / "main.py").parent.mkdir(parents=True)
    (comfy_root / "main.py").touch()
    python_executable = comfy_root / ".venv" / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    python_executable.touch()
    for parent in ("first", "second"):
        (
            comfy_root
            / ".venv"
            / parent
            / "comfyui_workflow_templates_media_image"
            / "templates"
        ).mkdir(parents=True)
    layout = ManagedComfyHarnessLayout.resolve(tmp_path, platform_name="posix")

    with pytest.raises(RuntimeError, match="resolve exactly once"):
        layout.image_template_root()
