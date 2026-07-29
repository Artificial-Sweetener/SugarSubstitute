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

"""Contract tests for the paired local canvas editable-installation tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.install_local_canvas_editables import (
    install_local_canvas_editables,
    local_canvas_package_roots,
)


def test_install_uses_one_paired_no_dependency_editable_overlay(tmp_path: Path) -> None:
    """The development installer must overlay both split packages together."""

    qpane_root = _write_qpane_checkout(tmp_path / "qpane")
    commands: list[tuple[str, ...]] = []

    install_local_canvas_editables(
        python_executable=tmp_path / "venv" / "python.exe",
        qpane_root=qpane_root,
        runner=lambda command: commands.append(tuple(command)),
    )

    qpane_package, cutecanvas_package = local_canvas_package_roots(qpane_root)
    assert commands[0][:5] == (
        str((tmp_path / "venv" / "python.exe").resolve()),
        "-m",
        "pip",
        "install",
        "PySide6==6.11.1",
    )
    assert not any(
        requirement.startswith(("qpane", "cutecanvas")) for requirement in commands[0]
    )
    assert commands[1:3] == [
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
    assert commands[3][1] == "-c"
    assert "import cutecanvas, qpane" in commands[3][2]


def test_package_root_validation_rejects_an_incomplete_checkout(tmp_path: Path) -> None:
    """An incomplete sibling checkout must fail before pip mutates the environment."""

    with pytest.raises(FileNotFoundError, match="Local canvas package"):
        local_canvas_package_roots(tmp_path / "missing")


def _write_qpane_checkout(root: Path) -> Path:
    """Create the minimal paired package structure used by this contract test."""

    for package in ("qpane", "cutecanvas"):
        package_root = root / "packages" / package
        package_root.mkdir(parents=True)
        (package_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return root
