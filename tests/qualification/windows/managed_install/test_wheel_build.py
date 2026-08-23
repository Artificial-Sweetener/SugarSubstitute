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

"""Qualify real wheel building through managed-install path boundaries."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from substitute.infrastructure.comfy.managed_install_environment import (
    build_managed_install_environment,
)
from substitute.infrastructure.comfy.managed_install_scratch import (
    MANAGED_INSTALL_PATH_CONTRACT,
    allocate_managed_install_scratch,
)
from sugarsubstitute_shared.windows_long_paths import operational_path, subprocess_path


@pytest.mark.platforms("windows")
def test_real_wheel_build_uses_budgeted_scratch_below_long_installation(
    tmp_path: Path,
) -> None:
    """Pip should build a SugarCubes-shaped wheel without deep temporary paths."""

    installation_root = operational_path(tmp_path / "Artificial Sweetener")
    while len(str(installation_root)) < 170:
        installation_root /= "deep-install-segment"
    project_root = installation_root / "comfyui" / "custom_nodes" / "SugarCubes"
    package_root = project_root / "sugarcubes"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text(
        '__version__ = "0.11.0"\n',
        encoding="utf-8",
    )
    (project_root / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools"]\n'
        'build-backend = "setuptools.build_meta"\n'
        "\n"
        "[project]\n"
        'name = "SugarCubes"\n'
        'version = "0.11.0"\n'
        "\n"
        "[tool.setuptools]\n"
        'packages = ["sugarcubes"]\n',
        encoding="utf-8",
    )
    install_target = tmp_path / "installed"
    scratch = allocate_managed_install_scratch(installation_root)
    try:
        env = build_managed_install_environment(scratch.root)
        result = subprocess.run(  # noqa: S603
            [
                subprocess_path(Path(sys.executable)),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-build-isolation",
                "--target",
                subprocess_path(install_target),
                subprocess_path(project_root),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=180,
        )

        assert MANAGED_INSTALL_PATH_CONTRACT.accepts(scratch.root)
        assert result.returncode == 0, result.stdout
        assert (install_target / "sugarcubes" / "__init__.py").is_file()
    finally:
        scratch.cleanup()

    assert not scratch.root.exists()
