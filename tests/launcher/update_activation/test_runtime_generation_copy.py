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

"""Prove runtime reuse cannot copy generation-bound uv and venv paths."""

from pathlib import Path

from launcher.sugarsubstitute_launcher.runtime_generation_copy import (
    copy_reusable_runtime,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime_policy import managed_venv_matches


def test_runtime_copy_retains_immutable_assets_and_rebuilds_bound_paths(
    tmp_path: Path,
) -> None:
    """Exclude both real uv aliases and dereferenced aliases from a candidate."""

    source = tmp_path / "previous" / "runtime"
    destination = tmp_path / "candidate" / "runtime"
    _write(source / "uv" / "uv.exe", "uv")
    _write(
        source / "python" / "cpython-3.13.12-windows-x86_64-none" / "python.exe",
        "python",
    )
    _write(
        source / "python" / "cpython-3.13-windows-x86_64-none" / "python.exe",
        "dereferenced junction",
    )
    _write(source / "python" / ".temp" / "partial", "partial")
    _write(source / ".venv" / "pyvenv.cfg", "home = previous")

    copy_reusable_runtime(source=source, destination=destination)

    assert (destination / "uv" / "uv.exe").read_text() == "uv"
    assert (
        destination / "python" / "cpython-3.13.12-windows-x86_64-none" / "python.exe"
    ).read_text() == "python"
    assert not (destination / "python" / "cpython-3.13-windows-x86_64-none").exists()
    assert not (destination / "python" / ".temp").exists()
    assert (destination / ".venv" / "pyvenv.cfg").read_text() == "home = previous"


def test_copied_venv_must_target_current_generation_python(tmp_path: Path) -> None:
    """Force runtime provisioning to rebuild venv launchers copied from history."""

    layout = InstallLayout.from_root(tmp_path / "candidate")
    layout.runtime_python.parent.mkdir(parents=True)
    layout.runtime_python.write_text("python", encoding="utf-8")
    config = layout.runtime_dir / ".venv" / "pyvenv.cfg"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "implementation = CPython\n"
        "version_info = 3.13.12\n"
        f"home = {tmp_path / 'previous' / 'runtime' / 'python' / 'cpython'}\n",
        encoding="utf-8",
    )

    assert not managed_venv_matches(layout=layout, python_version="3.13.12")

    config.write_text(
        "implementation = CPython\n"
        "version_info = 3.13.12\n"
        f"home = {layout.runtime_dir / 'python' / 'cpython'}\n",
        encoding="utf-8",
    )
    assert managed_venv_matches(layout=layout, python_version="3.13.12")


def _write(path: Path, content: str) -> None:
    """Create one deterministic runtime fixture file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
