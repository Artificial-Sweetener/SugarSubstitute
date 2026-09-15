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

"""Keep recovery inside one launch mode and installation despite shared executables."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.application_process_discovery import (
    InstalledInvocationScope,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


@pytest.mark.parametrize(
    "arguments",
    [[], ["--repair"], ["--no-update-check"], ["--continue-install"]],
)
def test_normal_owned_invocations_are_recoverable(
    tmp_path: Path, arguments: list[str]
) -> None:
    """Recognize application and interactive setup owners from the shared grammar."""
    scope = InstalledInvocationScope(InstallLayout.from_root(tmp_path))
    assert scope.accepts(["SugarSubstitute", *arguments], tmp_path)


@pytest.mark.parametrize("style", ["absolute", "relative", "equals"])
@pytest.mark.parametrize("matching", [True, False])
def test_explicit_root_must_match_recovery_installation(
    tmp_path: Path,
    style: str,
    matching: bool,
) -> None:
    """A shared executable cannot authorize recovery of another installation root."""
    root = tmp_path / "installed"
    selected = root if matching else tmp_path / "other"
    value = (
        str(selected.relative_to(tmp_path)) if style == "relative" else str(selected)
    )
    arguments = (
        [f"--install-root={value}"] if style == "equals" else ["--install-root", value]
    )
    scope = InstalledInvocationScope(InstallLayout.from_root(root))
    assert scope.accepts(["SugarSubstitute", *arguments], tmp_path) is matching


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["app", "--help"],
        ["app", "--unknown"],
        ["app", "--install-root"],
        ["app", "--headless-install", "--install-root", "."],
        ["app", "--verify-release-connectivity"],
        ["app", "--launcher-ui-child"],
        ["app", "--show-crash-report", "incident", "--install-root", "."],
    ],
)
def test_unrelated_or_unverifiable_operations_are_rejected_quietly(
    tmp_path: Path,
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inspecting another process must neither exit nor print CLI help or errors."""
    scope = InstalledInvocationScope(InstallLayout.from_root(tmp_path))
    assert not scope.accepts(arguments, tmp_path)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
