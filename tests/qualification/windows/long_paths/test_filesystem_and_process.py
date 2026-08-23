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

"""Qualify Windows long-path filesystem and process boundaries."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

import pytest

from sugarsubstitute_shared.external_path_failure import (
    ExternalLongPathCompatibilityError,
    external_long_path_error,
)
from sugarsubstitute_shared.windows_long_paths import (
    WindowsPathComponentTooLongError,
    WindowsLongPath,
    extended_length_path,
    operational_path,
    subprocess_path,
)
from substitute.infrastructure.process.hidden_process_runner import run_command


def test_operational_path_preserves_logical_text_across_child_paths(
    tmp_path: Path,
) -> None:
    """Application text should stay normal while OS calls receive extended paths."""

    logical_root = tmp_path / "install"
    root = operational_path(logical_root)
    child = root / "user" / "projects"

    assert isinstance(root, WindowsLongPath)
    assert isinstance(child, WindowsLongPath)
    assert str(child) == str(logical_root / "user" / "projects")
    assert os.fspath(child) == extended_length_path(str(child))
    assert "\\\\?\\" not in str(child)


@pytest.mark.platforms("windows")
def test_operational_path_relative_derivatives_remain_filesystem_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Derived relative paths should not enter the absolute-only namespace."""

    root = operational_path(tmp_path / "nodepack")
    relative = (root / "package" / "module.py").relative_to(root)

    def reject_recursive_absolute_check(_path: WindowsLongPath) -> bool:
        """Prove filesystem conversion does not recurse through pathlib."""

        raise AssertionError("__fspath__ must not call Path.is_absolute()")

    monkeypatch.setattr(WindowsLongPath, "is_absolute", reject_recursive_absolute_check)

    assert isinstance(relative, WindowsLongPath)
    assert os.fspath(relative) == str(Path("package") / "module.py")


@pytest.mark.platforms("windows")
def test_operational_path_supports_owned_files_beyond_max_path(
    tmp_path: Path,
) -> None:
    """Owned filesystem operations should work beyond the legacy path limit."""

    root = operational_path(tmp_path / "long-path-root")
    deep_directory = root
    while len(str(deep_directory)) < 285:
        deep_directory /= "segment-0123456789abcdef"
    source = deep_directory / "source.txt"
    copied = deep_directory / "copied.txt"
    renamed = deep_directory / "renamed.txt"

    source.parent.mkdir(parents=True)
    source.write_text("long path", encoding="utf-8")
    shutil.copy2(source, copied)
    copied.replace(renamed)

    assert len(str(source)) > 260
    assert source.read_text(encoding="utf-8") == "long path"
    assert renamed.read_text(encoding="utf-8") == "long path"
    assert {path.name for path in deep_directory.iterdir()} == {
        "renamed.txt",
        "source.txt",
    }
    assert root.resolve() == root


@pytest.mark.platforms("windows")
def test_operational_path_rejects_an_unrepresentable_component(
    tmp_path: Path,
) -> None:
    """A single component beyond the filesystem limit should explain the limit."""

    with pytest.raises(WindowsPathComponentTooLongError, match="255 characters"):
        operational_path(tmp_path / ("x" * 256) / "file.txt")


@pytest.mark.platforms("windows")
def test_subprocess_path_uses_extended_namespace_only_when_required(
    tmp_path: Path,
) -> None:
    """Short venv paths should stay logical while long arguments bypass MAX_PATH."""

    short_path = tmp_path / "venv" / "Scripts" / "python.exe"
    long_path = tmp_path / "workspace"
    while len(str(long_path)) < 285:
        long_path /= "segment-0123456789abcdef"

    assert subprocess_path(short_path) == str(short_path.absolute())
    assert subprocess_path(long_path) == extended_length_path(str(long_path.absolute()))


@pytest.mark.platforms("windows")
def test_external_error_classifier_preserves_component_and_logical_path(
    tmp_path: Path,
) -> None:
    """Known third-party failures should retain actionable structured context."""

    long_path = tmp_path / ("segment" * 30) / ("nested" * 15)
    error = OSError("[WinError 206] The filename or extension is too long")

    classified = external_long_path_error(
        component="7-Zip",
        path=long_path,
        detail=error,
    )

    assert isinstance(classified, ExternalLongPathCompatibilityError)
    assert classified.component == "7-Zip"
    assert classified.path == long_path
    assert "WinError 206" in classified.detail


@pytest.mark.platforms("windows")
def test_hidden_python_process_runs_inside_long_working_directory(
    tmp_path: Path,
) -> None:
    """App-owned subprocess launches should receive extended executable and cwd paths."""

    working_directory = operational_path(tmp_path / "process")
    while len(str(working_directory)) < 285:
        working_directory /= "segment-0123456789abcdef"
    working_directory.mkdir(parents=True)
    proof_path = working_directory / "proof.txt"

    result = run_command(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('ok')",
            os.fspath(proof_path),
        ],
        cwd=working_directory,
        check=True,
    )

    assert result.returncode == 0
    assert proof_path.read_text(encoding="utf-8") == "ok"
