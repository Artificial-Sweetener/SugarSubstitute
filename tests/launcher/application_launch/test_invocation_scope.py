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
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


@pytest.mark.parametrize(
    "case",
    [
        "owned",
        "other-root",
        "other-request",
        "ui-helper",
        "invalid-version",
        "invalid-session",
        "normal-launch",
        "extra-argument",
        "forged-argv",
    ],
)
def test_copied_repair_scope_does_not_depend_on_a_retained_request(
    tmp_path: Path, case: str
) -> None:
    """A copied owner needs its exact executable namespace and dedicated invocation."""
    layout = InstallLayout.from_root(tmp_path / "installation", target=WINDOWS_X64)
    root = tmp_path / "other" if case == "other-root" else layout.root
    version = "unversioned" if case == "invalid-version" else "1.2.3"
    session = "unrelated" if case == "invalid-session" else "session-owned"
    bundle = root / ".repair" / "helper" / version / session / "bundle"
    executable = bundle / "SugarSubstitute.exe"
    if case == "ui-helper":
        executable = bundle / "launcher-bin" / "LauncherUi.exe"
    request = (
        (tmp_path / "other" if case == "other-request" else layout.root)
        / ".repair"
        / "prepared.json"
    )
    arguments = [str(executable), f"--execute-repair-request={request}"]
    if case == "normal-launch":
        arguments = [str(executable)]
    if case == "extra-argument":
        arguments.append("--repair")
    if case == "forged-argv":
        executable = tmp_path / "unrelated.exe"
    assert not request.exists()
    scope = InstalledInvocationScope(layout)
    assert scope.accepts_invocation(executable, arguments, tmp_path) is (
        case == "owned"
    )


@pytest.mark.parametrize(
    "arguments",
    [[], ["--repair"], ["--no-update-check"], ["--continue-install"]],
)
def test_normal_owned_invocations_are_recoverable(
    tmp_path: Path, arguments: list[str]
) -> None:
    """Recognize application and interactive setup owners from the shared grammar."""
    scope = InstalledInvocationScope(InstallLayout.from_root(tmp_path))
    scope_executable = InstallLayout.from_root(tmp_path).executable_path
    assert scope.accepts_invocation(
        scope_executable, ["SugarSubstitute", *arguments], tmp_path
    )


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
    scope_executable = InstallLayout.from_root(root).executable_path
    assert (
        scope.accepts_invocation(
            scope_executable, ["SugarSubstitute", *arguments], tmp_path
        )
        is matching
    )


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
    scope_executable = InstallLayout.from_root(tmp_path).executable_path
    assert not scope.accepts_invocation(scope_executable, arguments, tmp_path)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
