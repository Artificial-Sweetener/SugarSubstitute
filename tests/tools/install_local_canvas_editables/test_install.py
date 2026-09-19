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

"""Contract tests for the complete local canvas editable-installation tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.install_local_canvas_editables import (
    install_local_canvas_editables,
    local_canvas_package_roots,
)


def test_install_uses_one_cohesive_no_dependency_editable_overlay(
    tmp_path: Path,
) -> None:
    """Overlay the complete canvas stack with dependency resolution disabled."""

    canvas_root = _write_canvas_checkout(tmp_path / "CuteCanvas")
    commands: list[tuple[str, ...]] = []

    install_local_canvas_editables(
        python_executable=tmp_path / "venv" / "python.exe",
        canvas_root=canvas_root,
        runner=lambda command: commands.append(tuple(command)),
    )

    ferrastra_package, qpane_package, cutecanvas_package = local_canvas_package_roots(
        canvas_root
    )
    assert commands[0][:5] == (
        str((tmp_path / "venv" / "python.exe").resolve()),
        "-m",
        "pip",
        "install",
        "PySide6==6.11.2",
    )
    assert not any(
        requirement.startswith(("ferrastra", "qpane", "cutecanvas"))
        for requirement in commands[0]
    )
    assert commands[1:4] == [
        (
            str((tmp_path / "venv" / "python.exe").resolve()),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--editable",
            str(ferrastra_package),
        ),
        (
            str((tmp_path / "venv" / "python.exe").resolve()),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--editable",
            str(qpane_package),
        ),
        (
            str((tmp_path / "venv" / "python.exe").resolve()),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--editable",
            f"{cutecanvas_package}[sam]",
        ),
    ]
    assert commands[4][1] == "-c"
    assert "import cutecanvas, ferrastra, qpane" in commands[4][2]


def test_package_root_validation_rejects_an_incomplete_checkout(tmp_path: Path) -> None:
    """Fail before pip mutates the environment for incomplete checkouts."""

    with pytest.raises(FileNotFoundError, match="Local canvas package"):
        local_canvas_package_roots(tmp_path / "missing")


def _write_canvas_checkout(root: Path) -> Path:
    """Create the minimal canvas-stack package layout required by the tool."""

    for package in ("ferrastra", "qpane", "cutecanvas"):
        package_root = root / "packages" / package
        package_root.mkdir(parents=True)
        (package_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return root
